package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"
)

// llmModelOption describes one selectable entry in the `deploy llm` menu.
type llmModelOption struct {
	Tag       string
	Label     string
	SizeNote  string
	Warning   string
	Recommend bool
}

// Highest to lowest capability. Mainline Llama text models only — the
// specialized fine-tunes (tool-use, vision, guard, uncensored) in Ollama's
// library aren't a good fit for a generic "pick your capability tier" menu.
var llmModelOptions = []llmModelOption{
	{
		Tag:      "llama3.3:70b",
		Label:    "Llama 3.3 70B",
		SizeNote: "~43GB download",
		Warning:  "Needs ~64GB+ RAM — will be very slow or fail on typical laptops.",
	},
	{
		Tag:       "llama3.1:8b",
		Label:     "Llama 3.1 8B",
		SizeNote:  "~4.7GB download",
		Recommend: true,
	},
	{
		Tag:      "llama3.2:3b",
		Label:    "Llama 3.2 3B",
		SizeNote: "~2GB download",
		Warning:  "Lightweight and fast, lower answer quality.",
	},
	{
		Tag:      "llama3.2:1b",
		Label:    "Llama 3.2 1B",
		SizeNote: "~1.3GB download",
		Warning:  "Smallest and fastest, lowest answer quality.",
	},
}

// runDeployLLM implements `cloudgraph deploy llm [base-url]`: presents a
// menu of local Llama models, pulls the chosen one via Ollama, and connects
// CloudGraph to it by saving the choice to the API's settings endpoint —
// the same endpoint the (now-removed) Settings UI page used to write to.
func runDeployLLM(args []string) {
	baseURL := "http://localhost:8000"
	if len(args) > 0 && args[0] != "" {
		baseURL = strings.TrimSuffix(args[0], "/")
	}

	printHeader("Connect a local LLM to CloudGraph")

	inCluster := ollamaDeploymentExists()
	if !inCluster && !commandExists("ollama") {
		printError("ollama is not installed, and no in-cluster Ollama deployment was found.")
		printInfo("Either install Ollama locally (https://ollama.com/download) and re-run,")
		printInfo("or deploy CloudGraph's Helm chart first (it includes an in-cluster Ollama).")
		os.Exit(1)
	}
	if inCluster {
		printInfo("Found an in-cluster Ollama deployment (cloudgraph-system/ollama) — pulling into it.")
	}

	fmt.Println("Choose a model (highest to lowest capability):")
	for i, opt := range llmModelOptions {
		line := fmt.Sprintf("  %d) %s (%s)", i+1, opt.Label, opt.SizeNote)
		if opt.Recommend {
			line += " [recommended]"
		}
		fmt.Println(line)
		if opt.Warning != "" {
			fmt.Printf("     %s\n", opt.Warning)
		}
	}

	reader := bufio.NewReader(os.Stdin)
	var chosen *llmModelOption
	for chosen == nil {
		fmt.Printf("Choose option (1-%d): ", len(llmModelOptions))
		input, err := reader.ReadString('\n')
		if err != nil {
			printError("Failed to read input")
			os.Exit(1)
		}
		choice := strings.TrimSpace(input)
		idx, convErr := strconv.Atoi(choice)
		if convErr != nil || idx < 1 || idx > len(llmModelOptions) {
			printError("Invalid option")
			continue
		}
		selected := llmModelOptions[idx-1]
		chosen = &selected
	}

	printInfo(fmt.Sprintf(
		"Pulling %s — this may take a while depending on your connection...",
		chosen.Tag,
	))
	if err := pullModel(chosen.Tag, inCluster); err != nil {
		printError(fmt.Sprintf("Failed to pull %s: %v", chosen.Tag, err))
		os.Exit(1)
	}
	printSuccess(fmt.Sprintf("%s pulled successfully", chosen.Tag))

	printInfo("Connecting CloudGraph to the local model...")
	if err := saveLLMSettings(baseURL, chosen.Tag); err != nil {
		printError(fmt.Sprintf("Failed to connect CloudGraph to %s: %v", chosen.Tag, err))
		printWarning("Make sure the CloudGraph API is running and reachable at " + baseURL)
		os.Exit(1)
	}

	printSuccess(fmt.Sprintf("CloudGraph is now connected to %s", chosen.Tag))
}

// ollamaDeploymentExists reports whether an in-cluster Ollama Deployment
// (installed by this project's Helm chart, see deployments/helm/cloudgraph/
// templates/ollama.yaml) is reachable via kubectl. Used to decide whether
// to pull the model into that pod instead of assuming a local `ollama`
// binary — the same `cloudgraph deploy llm` command works unmodified for
// both a local dev setup and a full Kubernetes deployment.
func ollamaDeploymentExists() bool {
	if !commandExists("kubectl") {
		return false
	}
	_, err := commandOutput(
		"kubectl", "get", "deployment", "ollama",
		"-n", "cloudgraph-system", "-o", "name",
	)
	return err == nil
}

// pullModel pulls the given model tag either into the in-cluster Ollama
// pod (via kubectl exec, streamed live) or into a local Ollama install,
// depending on inCluster.
func pullModel(tag string, inCluster bool) error {
	if inCluster {
		return runCmd(
			"kubectl", "exec", "-n", "cloudgraph-system", "deploy/ollama",
			"--", "ollama", "pull", tag,
		)
	}
	return runCmd("ollama", "pull", tag)
}

// saveLLMSettings POSTs the chosen provider/model to CloudGraph's settings
// endpoint. api_key is always empty — Ollama needs none.
func saveLLMSettings(baseURL, model string) error {
	payload := map[string]string{
		"provider": "ollama",
		"api_key":  "",
		"model":    model,
	}
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Post(
		baseURL+"/api/v1/settings", "application/json", bytes.NewBuffer(payloadBytes),
	)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(body))
	}
	return nil
}

package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"runtime"
	"strings"
	"time"
)

var (
	CloudGraphVersion = "0.1.0"
	CloudGraphBuild   = "dev"
	CloudGraphCommit  = "unknown"
)

const (
	Red    = "\033[0;31m"
	Green  = "\033[0;32m"
	Yellow = "\033[1;33m"
	Blue   = "\033[0;34m"
	NC     = "\033[0m" // No Color
)

func printHeader(msg string) {
	fmt.Printf("%s===================================================%s\n", Blue, NC)
	fmt.Printf("%s%s%s\n", Blue, msg, NC)
	fmt.Printf("%s===================================================%s\n", Blue, NC)
}

func printSuccess(msg string) {
	fmt.Printf("%s✓ %s%s\n", Green, msg, NC)
}

func printError(msg string) {
	fmt.Printf("%s✗ %s%s\n", Red, msg, NC)
}

func printWarning(msg string) {
	fmt.Printf("%s⚠ %s%s\n", Yellow, msg, NC)
}

func printInfo(msg string) {
	fmt.Printf("%sℹ %s%s\n", Blue, msg, NC)
}

func showHelp() {
	helpText := `CloudGraph CLI

Usage:
  cloudgraph [command]

Commands:
  version        Show the installed CloudGraph version and build metadata
  doctor         Run CloudGraph system checks and environment validation
  status         Show CloudGraph deployment status and component health
  health         Check the CloudGraph API health endpoint
  ingest         Send a sample payload to the CloudGraph API
  deploy         Install Kubernetes (kubeadm), Helm, and CloudGraph
  uninstall      Uninstall CloudGraph and optionally dismantle the cluster
  help           Show this help message

Examples:
  cloudgraph version
  cloudgraph doctor
  cloudgraph status
  cloudgraph health http://localhost:8000
  cloudgraph ingest http://localhost:8000 /api/v1/telemetry/logs
  sudo cloudgraph deploy
  cloudgraph uninstall
`
	fmt.Print(helpText)
}

func showVersion() {
	fmt.Printf("🏷️ version: %s\n", CloudGraphVersion)
	fmt.Printf("🛠️ build: %s\n", CloudGraphBuild)
	fmt.Printf("📌 commit: %s\n", CloudGraphCommit)
}

func runHealth(args []string) {
	if len(args) < 1 {
		fmt.Fprintln(os.Stderr, "Usage: cloudgraph health <base-url>")
		os.Exit(1)
	}
	baseURL := strings.TrimSuffix(args[0], "/")

	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Get(baseURL + "/health")
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error connecting to health endpoint: %v\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error reading response body: %v\n", err)
		os.Exit(1)
	}

	fmt.Print(string(body))
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		os.Exit(1)
	}
}

func runIngest(args []string) {
	if len(args) < 2 {
		fmt.Fprintln(os.Stderr, "Usage: cloudgraph ingest <base-url> <endpoint>")
		os.Exit(1)
	}
	baseURL := strings.TrimSuffix(args[0], "/")
	endpoint := args[1]
	if !strings.HasPrefix(endpoint, "/") {
		endpoint = "/" + endpoint
	}

	payloadMap := map[string]interface{}{
		"pod_id":         "demo-pod",
		"pod_name":       "demo",
		"message":        "hello from cloudgraph cli",
		"level":          "info",
		"timestamp":      time.Now().Unix(),
		"container_name": "demo",
	}

	payloadBytes, err := json.Marshal(payloadMap)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error marshaling payload: %v\n", err)
		os.Exit(1)
	}

	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Post(baseURL+endpoint, "application/json", bytes.NewBuffer(payloadBytes))
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error connecting to ingest endpoint: %v\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error reading response body: %v\n", err)
		os.Exit(1)
	}

	fmt.Print(string(body))
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		os.Exit(1)
	}
}

func main() {
	if runtime.GOOS != "linux" && os.Getenv("CLOUDGRAPH_TESTING") != "true" {
		fmt.Fprintln(os.Stderr, "Error: CloudGraph is only supported on Linux.")
		os.Exit(1)
	}

	if len(os.Args) < 2 {
		showHelp()
		return
	}

	cmd := os.Args[1]
	cmdArgs := os.Args[2:]

	switch cmd {
	case "version":
		showVersion()
	case "health":
		runHealth(cmdArgs)
	case "ingest":
		runIngest(cmdArgs)
	case "deploy":
		runDeploy()
	case "doctor":
		runDoctor()
	case "status":
		runStatus()
	case "uninstall":
		runUninstall()
	case "help", "--help", "-h":
		showHelp()
	default:
		fmt.Fprintf(os.Stderr, "Unknown command: %s\n", cmd)
		showHelp()
		os.Exit(1)
	}
}

package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

// reportSettings mirrors the "settings" object inside GET /api/v1/settings.
type reportSettings struct {
	Provider string `json:"provider"`
	Model    string `json:"model"`
}

type reportSettingsResponse struct {
	Status   string         `json:"status"`
	Settings reportSettings `json:"settings"`
}

// reportStatusResponse mirrors GET /api/v1/research/report.
type reportStatusResponse struct {
	Status   string        `json:"status"` // idle | running | completed | failed
	Progress string        `json:"progress"`
	Error    string        `json:"error"`
	Result   *reportResult `json:"result"`
}

type reportResult struct {
	NScenarios              int               `json:"n_scenarios"`
	NExcluded               int               `json:"n_excluded"`
	NClaims                 int               `json:"n_claims"`
	ExcludedScenarios       []map[string]any  `json:"excluded_scenarios"`
	AgreementSummary        string            `json:"agreement_summary"`
	ContextConditionSummary map[string]string `json:"context_condition_summary"`
	ClaimsCSV               string            `json:"claims_csv"`
	AgreementCrosstabCSV    string            `json:"agreement_crosstab_csv"`
	NeurosymbolicCSV        string            `json:"neurosymbolic_csv"`
}

// runReport implements `cloudgraph report [--limit N] [base-url]`: generates
// CloudGraph's core research report (GPCS vs. self-consistency) by driving
// the API's background-job endpoints over HTTP — no local source checkout
// or Python environment needed. services/api/scripts/generate_research_report.py
// runs the same underlying logic directly for local-dev use against a full
// repo clone, if preferred.
func runReport(args []string) {
	baseURL := "http://localhost:8000"
	limit := 0

	for i := 0; i < len(args); i++ {
		switch args[i] {
		case "--limit":
			if i+1 >= len(args) {
				printError("--limit requires a value")
				os.Exit(1)
			}
			n, err := strconv.Atoi(args[i+1])
			if err != nil || n < 1 {
				printError("--limit must be a positive integer")
				os.Exit(1)
			}
			limit = n
			i++
		default:
			if args[i] != "" {
				baseURL = strings.TrimSuffix(args[i], "/")
			}
		}
	}

	printHeader("Generate CloudGraph Research Report")

	settings, err := fetchLLMSettings(baseURL)
	if err != nil {
		printError(fmt.Sprintf("Failed to reach CloudGraph API at %s: %v", baseURL, err))
		os.Exit(1)
	}
	if settings.Provider == "" || settings.Model == "" {
		printError("No local model connected.")
		printInfo("Run `cloudgraph deploy llm` to set one up, then re-run this command.")
		os.Exit(1)
	}
	printSuccess(fmt.Sprintf("Local model connected: %s", settings.Model))

	// A configured model isn't the same as a reachable one — check the
	// server's own view of Ollama connectivity (it knows the real
	// OLLAMA_BASE_URL for this deployment; the CLI's machine can't safely
	// guess it, since it's an in-cluster address in the Kubernetes case).
	ollamaReachable, err := checkOllamaReachable(baseURL)
	if err != nil {
		printError(fmt.Sprintf("Failed to check Ollama status via %s: %v", baseURL, err))
		os.Exit(1)
	}
	if !ollamaReachable {
		printError("Ollama is not reachable from CloudGraph right now.")
		printInfo("A model is configured, but the Ollama server itself isn't responding —")
		printInfo("check it's running (in-cluster: `kubectl get pods -n cloudgraph-system`,")
		printInfo("local: `ollama serve`) before starting a run that would otherwise just")
		printInfo("exclude every scenario after running the full stack for nothing.")
		os.Exit(1)
	}
	printSuccess("Ollama is reachable")

	if limit > 0 {
		printInfo(fmt.Sprintf("Starting report generation (pilot — %d scenario(s))...", limit))
	} else {
		printInfo("Starting report generation (full — 25 scenarios; this can take a long time on local CPU inference)...")
	}

	if err := startReportRun(baseURL, limit); err != nil {
		printError(fmt.Sprintf("Failed to start report run: %v", err))
		os.Exit(1)
	}

	final := waitForReport(baseURL)

	if final.Status == "failed" {
		printError(fmt.Sprintf("Report generation failed: %s", final.Error))
		os.Exit(1)
	}

	savedDir, err := saveReport(final.Result)
	if err != nil {
		printError(fmt.Sprintf("Report completed, but failed to save it locally: %v", err))
		os.Exit(1)
	}

	printSuccess("Report generation complete.")
	// n_excluded counts (scenario, context-condition) exclusion events, not
	// excluded scenarios — each scenario runs 3 conditions (none/raw/hybrid),
	// any of which can be excluded independently of the others.
	totalAttempts := final.Result.NScenarios * len(contextConditions)
	fmt.Printf("  Scenarios:           %d\n", final.Result.NScenarios)
	fmt.Printf("  Excluded attempts:   %d/%d (scenario x context-condition)\n",
		final.Result.NExcluded, totalAttempts)
	fmt.Printf("  Claims scored:       %d\n", final.Result.NClaims)
	fmt.Printf("  Agreement:           %s\n", final.Result.AgreementSummary)
	for _, condition := range contextConditions {
		if summary, ok := final.Result.ContextConditionSummary[condition]; ok {
			fmt.Printf("    context=%-6s %s\n", condition, summary)
		}
	}
	fmt.Printf("  Saved to:            %s\n", savedDir)
}

// contextConditions mirrors report_runner.py's CONTEXT_CONDITIONS — kept in
// sync manually since it's just used for display ordering/counting here,
// not sent to the API (the server decides what to run).
var contextConditions = []string{"none", "raw", "hybrid"}

// waitForReport polls until the run reaches a terminal state, printing each
// new progress update as it appears — this is the "simplest" option (the
// terminal stays tied up for the duration of the run, by design).
func waitForReport(baseURL string) *reportStatusResponse {
	lastProgress := ""
	for {
		time.Sleep(5 * time.Second)
		status, err := fetchReportStatus(baseURL)
		if err != nil {
			printWarning(fmt.Sprintf("Lost contact with API, retrying: %v", err))
			continue
		}
		if status.Progress != "" && status.Progress != lastProgress {
			fmt.Printf("  ... %s\n", status.Progress)
			lastProgress = status.Progress
		}
		if status.Status == "completed" || status.Status == "failed" {
			return status
		}
	}
}

func fetchLLMSettings(baseURL string) (*reportSettings, error) {
	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Get(baseURL + "/api/v1/settings")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	var parsed reportSettingsResponse
	if err := json.Unmarshal(body, &parsed); err != nil {
		return nil, fmt.Errorf("unexpected response: %s", string(body))
	}
	return &parsed.Settings, nil
}

// checkOllamaReachable asks the API's own /health endpoint whether it can
// reach Ollama — the server, not the CLI, knows the real OLLAMA_BASE_URL
// for whatever deployment this is (localhost in local dev, an in-cluster
// service address in the Kubernetes deployment).
func checkOllamaReachable(baseURL string) (bool, error) {
	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Get(baseURL + "/health")
	if err != nil {
		return false, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return false, err
	}
	var parsed struct {
		Ollama string `json:"ollama"`
	}
	if err := json.Unmarshal(body, &parsed); err != nil {
		return false, fmt.Errorf("unexpected response: %s", string(body))
	}
	return parsed.Ollama == "reachable", nil
}

func startReportRun(baseURL string, limit int) error {
	url := baseURL + "/api/v1/research/report"
	if limit > 0 {
		url = fmt.Sprintf("%s?limit=%d", url, limit)
	}
	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Post(url, "application/json", nil)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("unexpected status %d: %s", resp.StatusCode, string(body))
	}
	return nil
}

func fetchReportStatus(baseURL string) (*reportStatusResponse, error) {
	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Get(baseURL + "/api/v1/research/report")
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	var parsed reportStatusResponse
	if err := json.Unmarshal(body, &parsed); err != nil {
		return nil, fmt.Errorf("unexpected response: %s", string(body))
	}
	return &parsed, nil
}

// saveReport writes the completed report's contents to
// ~/.cloudgraph/reports/report-<timestamp>/ and returns that directory.
func saveReport(result *reportResult) (string, error) {
	if result == nil {
		return "", fmt.Errorf("no result to save")
	}

	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	dir := filepath.Join(home, ".cloudgraph", "reports",
		fmt.Sprintf("report-%s", time.Now().Format("2006-01-02T15-04-05")))
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}

	if err := os.WriteFile(filepath.Join(dir, "claims.csv"), []byte(result.ClaimsCSV), 0o644); err != nil {
		return "", err
	}
	if err := os.WriteFile(
		filepath.Join(dir, "agreement_crosstab.csv"),
		[]byte(result.AgreementCrosstabCSV), 0o644,
	); err != nil {
		return "", err
	}

	excludedJSON, err := json.MarshalIndent(result.ExcludedScenarios, "", "  ")
	if err != nil {
		return "", err
	}
	if err := os.WriteFile(filepath.Join(dir, "excluded_scenarios.json"), excludedJSON, 0o644); err != nil {
		return "", err
	}

	if err := os.WriteFile(
		filepath.Join(dir, "neurosymbolic_retrieval_detail.csv"),
		[]byte(result.NeurosymbolicCSV), 0o644,
	); err != nil {
		return "", err
	}

	var conditionLines strings.Builder
	for _, condition := range contextConditions {
		if s, ok := result.ContextConditionSummary[condition]; ok {
			conditionLines.WriteString(fmt.Sprintf("  context=%-6s %s\n", condition, s))
		}
	}

	totalAttempts := result.NScenarios * len(contextConditions)
	summary := fmt.Sprintf(
		"CloudGraph Research Report\n"+
			"==========================\n"+
			"Scenarios:           %d\n"+
			"Excluded attempts:   %d/%d (scenario x context-condition)\n"+
			"Claims scored:       %d\n"+
			"Agreement:           %s\n%s",
		result.NScenarios, result.NExcluded, totalAttempts,
		result.NClaims, result.AgreementSummary, conditionLines.String(),
	)
	if err := os.WriteFile(filepath.Join(dir, "summary.txt"), []byte(summary), 0o644); err != nil {
		return "", err
	}

	return dir, nil
}

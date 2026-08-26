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

// runReport implements `cloudgraph report [--limit N] [base-url]`: generates the
// GPCS vs. self-consistency report by driving the API's background-job endpoints
// over HTTP, so no checkout or Python env is needed. scripts/
// generate_research_report.py runs the same logic directly for local dev.
func runReport(args []string) {
	baseURL := "http://localhost:8000"
	explicitBaseURL := false
	limit := 0
	offset := 0

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
		case "--offset":
			if i+1 >= len(args) {
				printError("--offset requires a value")
				os.Exit(1)
			}
			n, err := strconv.Atoi(args[i+1])
			if err != nil || n < 0 {
				printError("--offset must be a non-negative integer")
				os.Exit(1)
			}
			offset = n
			i++
		default:
			if args[i] != "" {
				baseURL = strings.TrimSuffix(args[i], "/")
				explicitBaseURL = true
			}
		}
	}

	printHeader("Generate CloudGraph Research Report")

	// "localhost:8000" only matches local dev; on Kubernetes the API is behind
	// Ingress on the node's address. Skipped if the caller passed a URL.
	if !explicitBaseURL && cloudgraphAPIDeploymentExists() {
		if detected := detectClusterHostIP(); detected != "" {
			baseURL = "http://" + detected
			printInfo(fmt.Sprintf(
				"No base URL given — using the cluster node's address (%s) "+
					"instead of localhost, since that's a local-dev-only default.",
				baseURL,
			))
		}
	}

	settings, err := fetchLLMSettings(baseURL)
	if err != nil {
		printError(fmt.Sprintf("Failed to reach CloudGraph API at %s: %v", baseURL, err))
		os.Exit(1)
	}
	if settings.Provider == "" {
		printError("No LLM provider connected.")
		printInfo("Configure one on the Settings page, then re-run this command.")
		os.Exit(1)
	}
	modelDesc := settings.Model
	if modelDesc == "" {
		modelDesc = "provider default"
	}
	printSuccess(fmt.Sprintf("Provider connected: %s (%s)", settings.Provider, modelDesc))

	switch {
	case limit > 0 && offset > 0:
		printInfo(fmt.Sprintf(
			"Starting report generation (batch — scenarios %d-%d)...",
			offset+1, offset+limit,
		))
	case limit > 0:
		printInfo(fmt.Sprintf("Starting report generation (pilot — %d scenario(s))...", limit))
	case offset > 0:
		printInfo(fmt.Sprintf("Starting report generation (from scenario %d to the end)...", offset+1))
	default:
		printInfo("Starting report generation (full benchmark)...")
	}

	runStartTime := time.Now().UTC()

	if err := startReportRun(baseURL, limit, offset); err != nil {
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

	// Best-effort: pod logs are ephemeral and this directory is the one place
	// already saving durable output. Not fatal if kubectl or the deployments
	// are unreachable (e.g. non-Kubernetes local dev); the report itself has
	// already saved.
	if err := saveLLMLogs(savedDir, runStartTime); err != nil {
		printWarning(fmt.Sprintf("Could not save LLM call logs: %v", err))
	} else {
		printSuccess("LLM request/response logs saved alongside the report")
	}

	printSuccess("Report generation complete.")
	// n_excluded counts (scenario, condition) events, not scenarios: each
	// scenario runs 3 conditions that can be excluded independently.
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

// Mirrors report_runner.py's CONTEXT_CONDITIONS. Display only; the server
// decides what actually runs.
var contextConditions = []string{"none", "raw", "hybrid"}

// waitForReport polls to a terminal state, printing progress. The terminal
// stays tied up for the run, by design.
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

// detectClusterHostIP returns the node's InternalIP, which on the single-node
// kubeadm clusters this deploys is where Ingress is reachable. "" if unknown.
func detectClusterHostIP() string {
	if !commandExists("kubectl") {
		return ""
	}
	out, err := commandOutput(
		"kubectl", "get", "nodes",
		"-o", `jsonpath={.items[0].status.addresses[?(@.type=="InternalIP")].address}`,
	)
	if err != nil {
		return ""
	}
	return strings.TrimSpace(out)
}

// cloudgraphAPIDeploymentExists reports whether an in-cluster API Deployment is
// reachable, signalling that "localhost" is the wrong default base URL.
func cloudgraphAPIDeploymentExists() bool {
	if !commandExists("kubectl") {
		return false
	}
	_, err := commandOutput(
		"kubectl", "get", "deployment", "cloudgraph-api",
		"-n", "cloudgraph-system", "-o", "name",
	)
	return err == nil
}

// Services whose call_llm() prints [LLM REQUEST]/[LLM RESPONSE]. Manual list.
var llmLoggingDeployments = []string{"agent-orchestrator", "investigation-engine", "cloudgraph-api"}

// saveLLMLogs copies each LLM-calling service's pod logs into the report dir,
// scoped by --since-time. Pod logs are ephemeral, so this is the only durable
// copy. Saved as-is rather than filtered to [LLM ...] lines: with threaded
// servers a line-based filter can split a multi-line JSON payload.
func saveLLMLogs(dir string, since time.Time) error {
	if !commandExists("kubectl") {
		return fmt.Errorf("kubectl not available")
	}
	sinceArg := "--since-time=" + since.Format(time.RFC3339)
	var errs []string
	for _, deployment := range llmLoggingDeployments {
		out, err := commandOutput(
			"kubectl", "logs", "-n", "cloudgraph-system",
			"deploy/"+deployment, sinceArg,
		)
		if err != nil {
			errs = append(errs, fmt.Sprintf("%s: %v", deployment, err))
			continue
		}
		logPath := filepath.Join(dir, fmt.Sprintf("llm_logs_%s.log", deployment))
		if err := os.WriteFile(logPath, []byte(out), 0o644); err != nil {
			errs = append(errs, fmt.Sprintf("%s: %v", deployment, err))
		}
	}
	if len(errs) > 0 {
		return fmt.Errorf("%s", strings.Join(errs, "; "))
	}
	return nil
}

func startReportRun(baseURL string, limit int, offset int) error {
	url := baseURL + "/api/v1/research/report"
	params := []string{}
	if limit > 0 {
		params = append(params, fmt.Sprintf("limit=%d", limit))
	}
	if offset > 0 {
		params = append(params, fmt.Sprintf("offset=%d", offset))
	}
	if len(params) > 0 {
		url = fmt.Sprintf("%s?%s", url, strings.Join(params, "&"))
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

// saveReport writes to ~/.cloudgraph/reports/report-<timestamp>/ and returns it.
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
			fmt.Fprintf(&conditionLines, "  context=%-6s %s\n", condition, s)
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

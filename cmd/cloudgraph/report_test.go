package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func TestFetchLLMSettings(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/v1/settings" {
			t.Errorf("path = %q, want /api/v1/settings", r.URL.Path)
		}
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"success","settings":{"provider":"openai","api_key":"","model":"gpt-4o-mini"}}`))
	}))
	defer server.Close()

	settings, err := fetchLLMSettings(server.URL)
	if err != nil {
		t.Fatalf("fetchLLMSettings returned an error: %v", err)
	}
	if settings.Provider != "openai" {
		t.Errorf("Provider = %q, want openai", settings.Provider)
	}
	if settings.Model != "gpt-4o-mini" {
		t.Errorf("Model = %q, want gpt-4o-mini", settings.Model)
	}
}

func TestStartReportRunSendsLimitAsQueryParam(t *testing.T) {
	var receivedMethod, receivedQuery string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedMethod = r.Method
		receivedQuery = r.URL.RawQuery
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"started"}`))
	}))
	defer server.Close()

	if err := startReportRun(server.URL, 3, 0); err != nil {
		t.Fatalf("startReportRun returned an error: %v", err)
	}
	if receivedMethod != http.MethodPost {
		t.Errorf("method = %q, want POST", receivedMethod)
	}
	if receivedQuery != "limit=3" {
		t.Errorf("query = %q, want limit=3", receivedQuery)
	}
}

func TestStartReportRunOmitsLimitWhenZero(t *testing.T) {
	var receivedQuery string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedQuery = r.URL.RawQuery
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"started"}`))
	}))
	defer server.Close()

	if err := startReportRun(server.URL, 0, 0); err != nil {
		t.Fatalf("startReportRun returned an error: %v", err)
	}
	if receivedQuery != "" {
		t.Errorf("query = %q, want empty (no limit)", receivedQuery)
	}
}

func TestStartReportRunSendsLimitAndOffset(t *testing.T) {
	var receivedQuery string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedQuery = r.URL.RawQuery
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"started"}`))
	}))
	defer server.Close()

	if err := startReportRun(server.URL, 5, 10); err != nil {
		t.Fatalf("startReportRun returned an error: %v", err)
	}
	if receivedQuery != "limit=5&offset=10" {
		t.Errorf("query = %q, want limit=5&offset=10", receivedQuery)
	}
}

func TestStartReportRunSendsOffsetOnly(t *testing.T) {
	var receivedQuery string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedQuery = r.URL.RawQuery
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"started"}`))
	}))
	defer server.Close()

	if err := startReportRun(server.URL, 0, 20); err != nil {
		t.Fatalf("startReportRun returned an error: %v", err)
	}
	if receivedQuery != "offset=20" {
		t.Errorf("query = %q, want offset=20", receivedQuery)
	}
}

func TestFetchReportStatusParsesResult(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{
			"status": "completed",
			"progress": "done",
			"error": "",
			"result": {
				"n_scenarios": 25,
				"n_excluded": 2,
				"n_claims": 41,
				"excluded_scenarios": [{"scenario_id": "scenario-03", "reason": "x"}],
				"agreement_summary": "30/41 claims agree",
				"claims_csv": "a,b\n1,2\n",
				"agreement_crosstab_csv": "x,y\n1,2\n"
			}
		}`))
	}))
	defer server.Close()

	status, err := fetchReportStatus(server.URL)
	if err != nil {
		t.Fatalf("fetchReportStatus returned an error: %v", err)
	}
	if status.Status != "completed" {
		t.Errorf("Status = %q, want completed", status.Status)
	}
	if status.Result == nil {
		t.Fatal("Result is nil, want a populated result")
	}
	if status.Result.NClaims != 41 {
		t.Errorf("NClaims = %d, want 41", status.Result.NClaims)
	}
	if status.Result.AgreementSummary != "30/41 claims agree" {
		t.Errorf("AgreementSummary = %q, want %q", status.Result.AgreementSummary, "30/41 claims agree")
	}
}

func TestSaveReportWritesAllFiles(t *testing.T) {
	tmpHome := t.TempDir()
	t.Setenv("HOME", tmpHome)

	result := &reportResult{
		NScenarios:        25,
		NExcluded:         1,
		NClaims:           10,
		ExcludedScenarios: []map[string]any{{"scenario_id": "scenario-05", "reason": "x"}},
		AgreementSummary:  "8/10 claims agree",
		ContextConditionSummary: map[string]string{
			"none":   "5/6 claims agree (6 claims)",
			"raw":    "2/2 claims agree (2 claims)",
			"hybrid": "1/2 claims agree (2 claims)",
		},
		ClaimsCSV:            "scenario_id,context_condition,claim_id\nscenario-01,none,claim-1\n",
		AgreementCrosstabCSV: "claim_type,x\nstate,1\n",
		NeurosymbolicCSV:     "scenario_id,method\nscenario-01,keyword\n",
	}

	dir, err := saveReport(result)
	if err != nil {
		t.Fatalf("saveReport returned an error: %v", err)
	}

	wantDirPrefix := filepath.Join(tmpHome, ".cloudgraph", "reports")
	if filepath.Dir(dir) != wantDirPrefix {
		t.Errorf("saved dir = %q, want a child of %q", dir, wantDirPrefix)
	}

	for _, name := range []string{
		"claims.csv", "agreement_crosstab.csv", "excluded_scenarios.json",
		"neurosymbolic_retrieval_detail.csv", "summary.txt",
	} {
		path := filepath.Join(dir, name)
		if _, statErr := os.Stat(path); statErr != nil {
			t.Errorf("expected %s to exist: %v", path, statErr)
		}
	}

	excludedBytes, err := os.ReadFile(filepath.Join(dir, "excluded_scenarios.json"))
	if err != nil {
		t.Fatalf("failed to read excluded_scenarios.json: %v", err)
	}
	var excluded []map[string]any
	if err := json.Unmarshal(excludedBytes, &excluded); err != nil {
		t.Fatalf("excluded_scenarios.json is not valid JSON: %v", err)
	}
	if len(excluded) != 1 {
		t.Errorf("excluded_scenarios.json has %d entries, want 1", len(excluded))
	}
}

func TestSaveReportRejectsNilResult(t *testing.T) {
	if _, err := saveReport(nil); err == nil {
		t.Fatal("expected an error for a nil result, got nil")
	}
}

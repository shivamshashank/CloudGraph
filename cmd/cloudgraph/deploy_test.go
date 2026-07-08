package main

import (
	"bytes"
	"io"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestCommandExists(t *testing.T) {
	if !commandExists("ls") {
		t.Error("Expected 'ls' command to exist")
	}
	if commandExists("non-existent-command-12345") {
		t.Error("Expected 'non-existent-command-12345' command to not exist")
	}
}

func TestGetTotalMemoryGB(t *testing.T) {
	if runtime.GOOS != "linux" {
		t.Skip("Skipping memory detection test on non-Linux OS")
	}
	mem := getTotalMemoryGB()
	if mem <= 0 {
		t.Errorf("Expected total memory to be greater than 0, got %.2f", mem)
	}
}

func TestCopyFile(t *testing.T) {
	tmpSrc, err := os.CreateTemp("", "src_test_*.txt")
	if err != nil {
		t.Fatalf("Failed to create temp file: %v", err)
	}
	defer os.Remove(tmpSrc.Name())
	defer tmpSrc.Close()

	content := "hello world from unit tests"
	if _, err := tmpSrc.WriteString(content); err != nil {
		t.Fatalf("Failed to write to temp file: %v", err)
	}

	tmpDstPath := filepath.Join(os.TempDir(), "dst_test.txt")
	defer os.Remove(tmpDstPath)

	if err := copyFile(tmpSrc.Name(), tmpDstPath); err != nil {
		t.Fatalf("copyFile failed: %v", err)
	}

	dstContent, err := os.ReadFile(tmpDstPath)
	if err != nil {
		t.Fatalf("Failed to read dst file: %v", err)
	}

	if string(dstContent) != content {
		t.Errorf("Expected content %q, got %q", content, string(dstContent))
	}
}

func TestRunCmd(t *testing.T) {
	err := runCmd("echo", "test")
	if err != nil {
		t.Errorf("Expected runCmd of echo to succeed, got %v", err)
	}
	err = runCmd("non-existent-command-12345")
	if err == nil {
		t.Error("Expected runCmd of non-existent command to fail")
	}
}

func TestRunCmdInDir(t *testing.T) {
	tempDir := t.TempDir()
	err := runCmdInDir(tempDir, "echo", "test")
	if err != nil {
		t.Errorf("Expected runCmdInDir to succeed, got %v", err)
	}
}

func TestCommandOutput(t *testing.T) {
	out, err := commandOutput("echo", "hello")
	if err != nil {
		t.Errorf("Expected commandOutput of echo to succeed, got %v", err)
	}
	if out != "hello" {
		t.Errorf("Expected commandOutput to be 'hello', got %q", out)
	}
}

func TestCheckInternetConnection(t *testing.T) {
	_ = checkInternetConnection()
}

func TestGetKubectlCurrentContext(t *testing.T) {
	ctx := getKubectlCurrentContext()
	if ctx == "" {
		t.Error("Expected context to not be empty")
	}
}

func TestGetDeploymentStatuses(t *testing.T) {
	statuses := getDeploymentStatuses("default")
	if statuses == nil {
		t.Error("Expected map to be non-nil")
	}
}

func TestGetIngressHosts(t *testing.T) {
	hosts := getIngressHosts("default")
	if hosts == nil {
		t.Error("Expected slice to be non-nil")
	}
}

func TestParseQdrantCollectionPayload(t *testing.T) {
	payload := []byte(`{"result":{"collections":[{"name":"documents","status":"green","points_count":42},{"name":"embeddings","status":"yellow","pointsCount":7}]}}`)

	collections, err := parseQdrantCollectionPayload(payload)
	if err != nil {
		t.Fatalf("expected payload to parse, got error: %v", err)
	}
	if len(collections) != 2 {
		t.Fatalf("expected 2 collections, got %d", len(collections))
	}
	if collections[0].Name != "documents" || collections[0].Status != "green" || collections[0].Points != 42 {
		t.Fatalf("unexpected first collection payload: %+v", collections[0])
	}
	if collections[1].Name != "embeddings" || collections[1].Status != "yellow" || collections[1].Points != 7 {
		t.Fatalf("unexpected second collection payload: %+v", collections[1])
	}
}

func TestRunStatusIncludesQdrantCollections(t *testing.T) {
	oldContext := getKubectlCurrentContextFunc
	oldStatuses := getDeploymentStatusesFunc
	oldHosts := getIngressHostsFunc
	oldSummary := qdrantCollectionSummaryFunc
	defer func() {
		getKubectlCurrentContextFunc = oldContext
		getDeploymentStatusesFunc = oldStatuses
		getIngressHostsFunc = oldHosts
		qdrantCollectionSummaryFunc = oldSummary
	}()

	getKubectlCurrentContextFunc = func() string { return "test-context" }
	getDeploymentStatusesFunc = func(namespace string) map[string]string { return map[string]string{"api": "Running"} }
	getIngressHostsFunc = func(namespace string) []string { return []string{"cloudgraph.example.com"} }
	qdrantCollectionSummaryFunc = func(namespace string) []qdrantCollectionStatus {
		return []qdrantCollectionStatus{{Name: "documents", Status: "green", Points: 42}}
	}

	oldStdout := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	runStatus()

	w.Close()
	os.Stdout = oldStdout

	var buf bytes.Buffer
	_, _ = io.Copy(&buf, r)
	output := buf.String()

	if !strings.Contains(output, "CloudGraph Status Dashboard") {
		t.Fatalf("expected status banner in output, got: %s", output)
	}
	if !strings.Contains(output, "Vector Store") {
		t.Fatalf("expected vector store section in output, got: %s", output)
	}
	if !strings.Contains(output, "Qdrant collection documents") {
		t.Fatalf("expected Qdrant collection output, got: %s", output)
	}
}

func TestCheckKubectl(t *testing.T) {
	old := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	_ = checkKubectl()

	w.Close()
	os.Stdout = old

	var buf bytes.Buffer
	_, _ = io.Copy(&buf, r)
	output := buf.String()

	if !strings.Contains(output, "Checking for kubectl") {
		t.Error("Expected 'Checking for kubectl' in output")
	}
}

func TestCheckK8sCluster(t *testing.T) {
	old := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	_ = checkK8sCluster()

	w.Close()
	os.Stdout = old

	var buf bytes.Buffer
	_, _ = io.Copy(&buf, r)
	output := buf.String()

	if !strings.Contains(output, "Checking for Kubernetes cluster") {
		t.Error("Expected 'Checking for Kubernetes cluster' in output")
	}
}

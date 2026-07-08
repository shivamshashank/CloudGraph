package main

import (
	"bytes"
	"io"
	"os"
	"strings"
	"testing"
)

func init() {
	os.Setenv("CLOUDGRAPH_TESTING", "true")
}

func TestShowVersion(t *testing.T) {
	old := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	CloudGraphVersion = "1.2.3"
	CloudGraphBuild = "test-build"
	CloudGraphCommit = "abcdef0"

	showVersion()

	w.Close()
	os.Stdout = old

	var buf bytes.Buffer
	_, _ = io.Copy(&buf, r)
	output := buf.String()

	if !strings.Contains(output, "🏷️ version: 1.2.3") {
		t.Errorf("Expected version 1.2.3 in output, got: %s", output)
	}
	if !strings.Contains(output, "🛠️ build: test-build") {
		t.Errorf("Expected build test-build in output, got: %s", output)
	}
	if !strings.Contains(output, "📌 commit: abcdef0") {
		t.Errorf("Expected commit abcdef0 in output, got: %s", output)
	}
}

func TestMainVersionCommand(t *testing.T) {
	oldArgs := os.Args
	defer func() { os.Args = oldArgs }()

	os.Args = []string{"cloudgraph", "version"}

	old := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	CloudGraphVersion = "1.2.3"
	CloudGraphBuild = "test-build"
	CloudGraphCommit = "abcdef0"

	main()

	w.Close()
	os.Stdout = old

	var buf bytes.Buffer
	_, _ = io.Copy(&buf, r)
	output := buf.String()

	if !strings.Contains(output, "🏷️ version: 1.2.3") {
		t.Errorf("Expected version in main output, got: %s", output)
	}
}

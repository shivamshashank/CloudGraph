package main

import (
	"bytes"
	"io"
	"os"
	"strings"
	"testing"
)

func TestUninstallHelpers(t *testing.T) {
	old := os.Stdout
	r, w, _ := os.Pipe()
	os.Stdout = w

	uninstallHelmRelease()
	deleteNamespace()

	w.Close()
	os.Stdout = old

	var buf bytes.Buffer
	_, _ = io.Copy(&buf, r)
	output := buf.String()

	if !strings.Contains(output, "Step 1: Uninstalling CloudGraph Helm Release") {
		t.Error("Expected Step 1 header in output")
	}
	if !strings.Contains(output, "Step 2: Deleting CloudGraph Namespace") {
		t.Error("Expected Step 2 header in output")
	}
}

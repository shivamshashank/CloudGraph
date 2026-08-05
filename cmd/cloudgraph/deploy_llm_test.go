package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestLLMModelOptionsShape(t *testing.T) {
	if len(llmModelOptions) != 4 {
		t.Fatalf("expected exactly 4 model options, got %d", len(llmModelOptions))
	}

	recommendedCount := 0
	for i, opt := range llmModelOptions {
		if opt.Tag == "" || opt.Label == "" || opt.SizeNote == "" {
			t.Errorf("option %d has an empty Tag/Label/SizeNote: %+v", i, opt)
		}
		if opt.Recommend {
			recommendedCount++
		}
	}
	if recommendedCount != 1 {
		t.Errorf("expected exactly 1 recommended option, got %d", recommendedCount)
	}

	// Highest to lowest capability: 70b, 8b, 3b, 1b.
	wantOrder := []string{"llama3.3:70b", "llama3.1:8b", "llama3.2:3b", "llama3.2:1b"}
	for i, want := range wantOrder {
		if llmModelOptions[i].Tag != want {
			t.Errorf("option %d = %q, want %q", i, llmModelOptions[i].Tag, want)
		}
	}
}

func TestSaveLLMSettingsSendsCorrectPayload(t *testing.T) {
	var receivedMethod, receivedPath string
	var receivedBody map[string]string

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		receivedMethod = r.Method
		receivedPath = r.URL.Path
		_ = json.NewDecoder(r.Body).Decode(&receivedBody)
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(`{"status":"success"}`))
	}))
	defer server.Close()

	if err := saveLLMSettings(server.URL, "llama3.1:8b"); err != nil {
		t.Fatalf("saveLLMSettings returned an error: %v", err)
	}

	if receivedMethod != http.MethodPost {
		t.Errorf("method = %q, want POST", receivedMethod)
	}
	if receivedPath != "/api/v1/settings" {
		t.Errorf("path = %q, want /api/v1/settings", receivedPath)
	}
	if receivedBody["provider"] != "ollama" {
		t.Errorf("provider = %q, want ollama", receivedBody["provider"])
	}
	if receivedBody["model"] != "llama3.1:8b" {
		t.Errorf("model = %q, want llama3.1:8b", receivedBody["model"])
	}
	if receivedBody["api_key"] != "" {
		t.Errorf("api_key = %q, want empty (Ollama needs no key)", receivedBody["api_key"])
	}
}

func TestSaveLLMSettingsReturnsErrorOnNon2xx(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
		_, _ = w.Write([]byte(`{"detail":"boom"}`))
	}))
	defer server.Close()

	if err := saveLLMSettings(server.URL, "llama3.1:8b"); err == nil {
		t.Fatal("expected an error for a 500 response, got nil")
	}
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("settings-form");
  const providerSelect = document.getElementById("llm-provider");
  const apiKeyInput = document.getElementById("llm-api-key");
  const modelInput = document.getElementById("llm-model");
  const resetButton = document.getElementById("btn-reset-settings");
  const alertBox = document.getElementById("settings-alert");

  function showAlert(msg, isError = false) {
    alertBox.textContent = msg;
    alertBox.className = `alert-box ${isError ? "alert-error" : "alert-success"}`;
    alertBox.style.display = "block";
    setTimeout(() => {
      alertBox.style.display = "none";
    }, 5000);
  }

  // Load existing settings
  async function loadSettings() {
    try {
      const res = await fetch(`${window.CloudGraph.API_BASE}/api/v1/settings`);
      const data = await res.json();
      if (data.status === "success" && data.settings) {
        const settings = data.settings;
        if (settings.provider) providerSelect.value = settings.provider;
        if (settings.api_key) apiKeyInput.value = settings.api_key;
        if (settings.model) modelInput.value = settings.model;
      }
    } catch (err) {
      console.error("Failed to load settings from database:", err);
    }
  }
  loadSettings();

  // Handle Save
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const newSettings = {
      provider: providerSelect.value,
      api_key: apiKeyInput.value.trim(),
      model: modelInput.value.trim(),
    };

    if (!newSettings.api_key) {
      showAlert("Please provide an API Key.", true);
      return;
    }

    try {
      const res = await fetch(`${window.CloudGraph.API_BASE}/api/v1/settings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newSettings),
      });
      const data = await res.json();
      if (data.status === "success") {
        showAlert("LLM settings saved successfully!");
      } else {
        showAlert("Failed to save LLM settings.", true);
      }
    } catch (err) {
      console.error("Failed to save settings:", err);
      showAlert("Failed to save LLM settings.", true);
    }
  });

  // Handle Reset / Clear
  resetButton.addEventListener("click", async () => {
    try {
      const res = await fetch(`${window.CloudGraph.API_BASE}/api/v1/settings`, {
        method: "DELETE",
      });
      const data = await res.json();
      if (data.status === "success") {
        providerSelect.value = "openai";
        apiKeyInput.value = "";
        modelInput.value = "";
        showAlert("LLM credentials cleared successfully!");
      } else {
        showAlert("Failed to clear LLM settings.", true);
      }
    } catch (err) {
      console.error("Failed to clear settings:", err);
      showAlert("Failed to clear LLM settings.", true);
    }
  });
});

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
  const settings = JSON.parse(
    localStorage.getItem("cloudgraph_llm_settings") || "{}",
  );
  if (settings.provider) providerSelect.value = settings.provider;
  if (settings.api_key) apiKeyInput.value = settings.api_key;
  if (settings.model) modelInput.value = settings.model;

  // Handle Save
  form.addEventListener("submit", (e) => {
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

    localStorage.setItem(
      "cloudgraph_llm_settings",
      JSON.stringify(newSettings),
    );
    showAlert("LLM settings saved successfully!");
  });

  // Handle Reset / Clear
  resetButton.addEventListener("click", () => {
    localStorage.removeItem("cloudgraph_llm_settings");
    providerSelect.value = "openai";
    apiKeyInput.value = "";
    modelInput.value = "";
    showAlert("LLM credentials cleared successfully!");
  });
});

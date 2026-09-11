(async () => {
  try {
    await import("./food-scanner-i18n.js");
    await import("./food-scanner-card.js");
  } catch (error) {
    console.error("VeSync Local BT food scanner failed to load", error);
  }
})();

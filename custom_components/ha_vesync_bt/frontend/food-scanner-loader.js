(async () => {
  try {
    const revision = "0.2.0b2-r5";
    await import(`./food-scanner-i18n.js?v=${revision}`);
    await import(`./food-scanner-card-v2.js?v=${revision}`);
  } catch (error) {
    console.error("VeSync Local BT food scanner failed to load", error);
  }
})();

(async () => {
  try {
    const revision = "0.2.0b2-r2";
    await import(`./food-scanner-i18n.js?v=${revision}`);
    await import(`./food-scanner-card.js?v=${revision}`);
  } catch (error) {
    console.error("VeSync Local BT food scanner failed to load", error);
  }
})();

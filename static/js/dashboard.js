/**
 * Global UI helpers: Bootstrap tooltips (and future dashboard widgets).
 */
document.addEventListener("DOMContentLoaded", () => {
  if (typeof bootstrap === "undefined" || !bootstrap.Tooltip) {
    return;
  }
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => {
    try {
      new bootstrap.Tooltip(el);
    } catch (_) {
      /* ignore duplicate init */
    }
  });
});

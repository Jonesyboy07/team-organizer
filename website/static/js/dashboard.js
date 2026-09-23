document.addEventListener("DOMContentLoaded", () => {
    const root = document.getElementById("react-root");
    if (!root) {
        return;
    }

    root.textContent = `React widgets will mount here after Discord auth is wired into the Flask app on port ${root.dataset.port}.`;
});

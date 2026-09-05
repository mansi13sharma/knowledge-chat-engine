// Minimal history-API navigation helper shared by App.jsx's router shell and
// anything else that needs to change routes ("/" chat <-> "/admin" dashboard)
// without a routing library.
export function navigate(path) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

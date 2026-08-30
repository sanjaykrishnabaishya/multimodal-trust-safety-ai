function resolveDefaultApiBaseUrl() {
  if (typeof window === "undefined") {
    return "";
  }

  if (import.meta.env.DEV) {
    return (
      `${window.location.protocol}//` +
      `${window.location.hostname}:8010`
    );
  }

  return "";
}


const configuredApiBaseUrl =
  import.meta.env.VITE_API_BASE_URL
    ?.trim()
    .replace(/\/$/, "");


export const API_BASE_URL =
  configuredApiBaseUrl ||
  resolveDefaultApiBaseUrl();


export function buildApiUrl(path) {
  const normalizedPath =
    path.startsWith("/")
      ? path
      : `/${path}`;

  return `${API_BASE_URL}${normalizedPath}`;
}

// Public settings, baked in at build time. Defaults are the production values.
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "https://ai-api.artifact-network.org";
export const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "https://ai.artifact-network.org";
export const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL ?? "ai@artifact-network.org";
export const STATUS_URL = process.env.NEXT_PUBLIC_STATUS_URL ?? "https://status.artifact-network.org";
export const DOCS_URL = "https://github.com/aghribi";

// mwl_ is the prefix of keys issued before the ag_ rename; those keys stay valid.
export const isApiKey = (key: string) => key.startsWith("ag_") || key.startsWith("mwl_");

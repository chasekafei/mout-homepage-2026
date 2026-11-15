const TLS_COMPATIBILITY_ALIASES = new Set(["prefer", "require", "verify-ca"]);

/** pg 8 currently maps these aliases to verify-full; make that security behavior explicit. */
export function normalizeDatabaseConnectionString(connectionString: string): string {
  try {
    const url = new URL(connectionString);
    if (url.protocol !== "postgres:" && url.protocol !== "postgresql:") return connectionString;
    const sslMode = url.searchParams.get("sslmode")?.toLowerCase();
    if (sslMode && TLS_COMPATIBILITY_ALIASES.has(sslMode)) url.searchParams.set("sslmode", "verify-full");
    return url.toString();
  } catch {
    return connectionString;
  }
}

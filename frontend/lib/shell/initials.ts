export function getInitials(name: string | null | undefined, email: string): string {
  const trimmed = name?.trim();

  if (trimmed) {
    const parts = trimmed.split(/\s+/).filter(Boolean);
    const first = parts[0] ?? "";
    const last = parts.length > 1 ? (parts[parts.length - 1] ?? "") : "";
    const initials = `${first.charAt(0)}${last.charAt(0)}`.toUpperCase();

    if (initials.length > 0) {
      return initials;
    }
  }

  return email.trim().charAt(0).toUpperCase() || "?";
}

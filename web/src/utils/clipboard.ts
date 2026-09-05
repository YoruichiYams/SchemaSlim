/**
 * Safe clipboard copy utility with automatic fallback.
 * Supports modern Clipboard API (navigator.clipboard) and falls back
 * to document.execCommand('copy') in non-HTTPS or restricted iframe contexts.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  // 1. Try modern async Clipboard API if available in secure contexts
  if (typeof navigator !== 'undefined' && navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Fall through to legacy textarea fallback
    }
  }

  // 2. Fallback via temporary hidden textarea and document.execCommand
  if (typeof document !== 'undefined') {
    try {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      // Prevent scrolling to bottom of page in iOS/Safari
      textarea.style.position = 'fixed';
      textarea.style.top = '0';
      textarea.style.left = '0';
      textarea.style.width = '2em';
      textarea.style.height = '2em';
      textarea.style.padding = '0';
      textarea.style.border = 'none';
      textarea.style.outline = 'none';
      textarea.style.boxShadow = 'none';
      textarea.style.background = 'transparent';
      textarea.style.opacity = '0';
      textarea.setAttribute('readonly', '');
      textarea.setAttribute('aria-hidden', 'true');

      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      textarea.setSelectionRange(0, textarea.value.length);

      const successful = document.execCommand('copy');
      document.body.removeChild(textarea);
      return successful;
    } catch {
      return false;
    }
  }

  return false;
}

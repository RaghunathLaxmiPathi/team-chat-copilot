/* Safe message rendering: escape everything first, then apply a small set of rules (FR-21, DD-10). */
(function (root) {
  "use strict";

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function renderInline(escaped, mentionNames) {
    // Inline code first, so nothing inside it is formatted.
    return escaped
      .split(/(`[^`\n]+`)/)
      .map(function (part, i) {
        if (i % 2 === 1) return "<code>" + part.slice(1, -1) + "</code>";
        part = part.replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/gi, function (m, label, url) {
          return '<a href="' + url + '" target="_blank" rel="noopener noreferrer">' + label + "</a>";
        });
        part = part.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
        part = part.replace(/(^|[^*\w])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>");
        if (mentionNames) {
          part = part.replace(/(^|[^\w@])@([A-Za-z0-9._-]{3,32})/g, function (m, pre, name) {
            var key = name.toLowerCase();
            var trimmed = key.replace(/[._-]+$/, "");
            if (mentionNames.has(key)) {
              return pre + '<span class="mention">@' + name + "</span>";
            }
            if (mentionNames.has(trimmed)) {
              return pre + '<span class="mention">@' + name.slice(0, trimmed.length) + "</span>" + name.slice(trimmed.length);
            }
            return m;
          });
        }
        return part.replace(/\n/g, "<br>");
      })
      .join("");
  }

  function renderMarkdown(text, mentionNames) {
    var names = mentionNames ? new Set(Array.from(mentionNames, function (n) { return String(n).toLowerCase(); })) : null;
    return String(text == null ? "" : text)
      .split(/```([\s\S]*?)```/)
      .map(function (segment, i) {
        if (i % 2 === 1) return "<pre><code>" + escapeHtml(segment.replace(/^\n/, "")) + "</code></pre>";
        return renderInline(escapeHtml(segment), names);
      })
      .join("");
  }

  var api = { renderMarkdown: renderMarkdown, escapeHtml: escapeHtml };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ChatRender = api;
})(typeof window !== "undefined" ? window : globalThis);

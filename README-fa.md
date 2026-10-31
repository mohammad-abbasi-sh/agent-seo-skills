# agent-seo-skills

**به ایجنت هوش مصنوعی‌تان دست‌های سئو بدهید.** مجموعه‌ای در حال رشد از [اسکیل‌های ایجنت](https://agentskills.io) + یک سرور MCP که Claude Code، Claude Desktop، Cursor، Codex و بقیه ایجنت‌ها را به یک اپراتور سئو تبدیل می‌کند — لوکال‌محور، بدون API key، بدون هیچ وابستگی (فقط استانداردلایب پایتون).

بیشتر ابزارهای سئو برای ایجنت‌ها به API key پولی یا اتصال OAuth نیاز دارند. این پک روی هر URL عمومی کار می‌کند، آفلاین‌دوست است و با اسکریپت‌های قطعی که ایجنت اجرا می‌کند و می‌خواند — بدون هیچ متریک ساختگی، هرگز.

## چه چیزی داخلش است (نسخه ۰٫۲)

| بخش | چه کار می‌کند |
|---|---|
| `skills/site-audit` | اسکیل ایجنت: ممیزی هر صفحه (title، meta، H1، canonical، robots، OG، JSON-LD، تصاویر/alt، لینک‌ها، تعداد کلمات) ← امتیاز ۰ تا ۱۰۰ + اصلاحات اولویت‌بندی‌شده |
| `skills/striking-distance` | اسکیل ایجنت: تحلیل CSV خروجی سرچ کنسول — کوئری‌های striking-distance (رتبه ۸ تا ۲۰)، فرصت‌های CTR در برابر هم‌رتبه‌ها، کنیبالیزیشن کلمات کلیدی |
| `mcp-server/` | سرور MCP بدون وابستگی که همان موتور ممیزی را به‌صورت ابزار `audit_url` در اختیار هر کلاینت MCP می‌گذارد |

در نقشه راه (هر هفته یک اسکیل جدید): `schema-forge` (سازنده JSON-LD)، `ai-visibility-check` (آمادگی برای خزنده‌های هوش مصنوعی و llms.txt)، `persian-keyword-tools` (نرمال‌سازی و خوشه‌بندی کلمات کلیدی فارسی با Hazm).

## استفاده در Claude Code

اسکیل را در پوشه اسکیل‌هایتان کپی کنید:

```bash
git clone https://github.com/mohammad-abbasi-sh/agent-seo-skills
cp -r agent-seo-skills/skills/site-audit ~/.claude/skills/
```

بعد فقط از Claude بپرسید: **"Audit https://example.com for SEO"** — اسکیل لود می‌شود، اسکریپت ممیزی را اجرا می‌کند و امتیاز را با اصلاحات اولویت‌بندی‌شده گزارش می‌دهد.

## استفاده به‌عنوان سرور MCP (Claude Desktop / Claude Code / Cursor)

```bash
claude mcp add agent-seo -- python3 /path/to/agent-seo-skills/mcp-server/seo_mcp_server.py
```

در Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "agent-seo": {
      "command": "python3",
      "args": ["/path/to/agent-seo-skills/mcp-server/seo_mcp_server.py"]
    }
  }
}
```

بعد بپرسید: **"Use audit_url on https://example.com"**.

## اجرای مستقیم (بدون ایجنت)

```bash
python3 skills/site-audit/scripts/seo_audit.py https://example.com --json
python3 skills/striking-distance/scripts/gsc_analyze.py <gsc-export.csv>
```

## تست‌ها

```bash
python3 -m unittest discover -s tests -v
```

تست end-to-end هرمتیک: یک صفحه فیكسچر را به‌صورت لوکال سرو می‌کند، handshake مکانیزم MCP را انجام می‌دهد، `audit_url` را صدا می‌زند و گزارش را اعتبارسنجی می‌کند.

## اصول

- **ابزار قطعی، خروجی صادقانه.** اسکریپت‌ها اندازه می‌گیرند؛ ایجنت تفسیر می‌کند. بدون ترافیک، حجم جستجو یا عدد بک‌لینک ساختگی.
- **لوکال‌محور.** بدون API key، بدون حساب کاربری، بدون تله‌متری.
- **ساخته‌شده در ملأ عام، هر هفته یک اسکیل** توسط [محمد عباسی](https://github.com/mohammad-abbasi-sh) — مدیر سئو و مدیر محصول، در لبه سئو × هوش مصنوعی.

## لایسنس

MIT

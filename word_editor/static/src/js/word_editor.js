/** @odoo-module **/
/**
 * Word Editor — Main OWL Component
 * Full-featured Word Processor client action for Odoo 19
 */

import { Component, useState, useRef, onMounted, onWillUnmount, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";

// ─── Constants ──────────────────────────────────────────────────────────────

const FONTS = [
    "Arial", "Arial Black", "Comic Sans MS", "Courier New",
    "Georgia", "Impact", "Lucida Console", "Palatino Linotype",
    "Tahoma", "Times New Roman", "Trebuchet MS", "Verdana",
];

const FONT_SIZES = ["8","9","10","11","12","14","16","18","20","22","24","26","28","32","36","40","48","60","72"];

const HEADINGS = [
    { label: "Normal",      cmd: "p" },
    { label: "Heading 1",   cmd: "h1" },
    { label: "Heading 2",   cmd: "h2" },
    { label: "Heading 3",   cmd: "h3" },
    { label: "Heading 4",   cmd: "h4" },
    { label: "Heading 5",   cmd: "h5" },
    { label: "Heading 6",   cmd: "h6" },
    { label: "Blockquote",  cmd: "blockquote" },
    { label: "Preformatted",cmd: "pre" },
];

const COLORS = [
    "#000000","#ffffff","#ff0000","#00ff00","#0000ff","#ffff00",
    "#ff00ff","#00ffff","#ff8800","#8800ff","#00ff88","#ff0088",
    "#1a365d","#2c5282","#4a90d9","#68d391","#f6ad55","#fc8181",
    "#63b3ed","#b794f4","#f687b3","#4fd1c5","#fbd38d","#e2e8f0",
];

// ─── Utility ────────────────────────────────────────────────────────────────

function stripHtml(html) {
    const tmp = document.createElement("div");
    tmp.innerHTML = html || "";
    return tmp.textContent || tmp.innerText || "";
}

function wordCount(html) {
    const text = stripHtml(html).trim();
    return text ? text.split(/\s+/).filter(Boolean).length : 0;
}

function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value || "";
    return div.innerHTML;
}

function escapeAttribute(value) {
    return escapeHtml(value).replace(/"/g, "&quot;");
}

function normalizeUrl(value) {
    const url = (value || "").trim();
    if (!url || url === "https://") {
        return "";
    }
    if (/^(https?:|mailto:|tel:)/i.test(url)) {
        return url;
    }
    return `https://${url}`;
}

// ─── WordEditorAction ────────────────────────────────────────────────────────

export class WordEditorAction extends Component {
    static template = "word_editor.WordEditorAction";

    setup() {
        this.orm          = useService("orm");
        this.notification = useService("notification");
        this.action       = useService("action");

        // Editor state
        this.state = useState({
            // Document
            docId:       null,
            title:       "Untitled Document",
            isDirty:     false,
            isSaving:    false,
            savedAt:     null,
            isLoading:   false,

            // Toolbar state (reflects current selection)
            bold:        false,
            italic:      false,
            underline:   false,
            strike:      false,
            currentFont: "Arial",
            currentSize: "12",
            currentHeading: "p",
            textColor:   "#000000",
            hiliteColor: "#ffff00",

            // UI state
            zoom:        100,
            showColorPicker:  false,
            colorPickerType:  "text",   // 'text' | 'hilite'
            showFindReplace:  false,
            showTableModal:   false,
            showInsertLink:   false,
            showInsertImage:  false,
            showTemplates:    false,

            // Find & Replace
            findText:    "",
            replaceText: "",

            // Table insertion
            tableRows:   3,
            tableCols:   3,

            // Insert Link
            linkUrl:     "",
            linkText:    "",

            // Insert Image
            imageUrl:    "",

            // Statistics
            wordCount:    0,
            charCount:    0,
            readingTime:  0,

            // Templates
            templates:    [],
        });

        this.editorRef    = useRef("editorArea");
        this.titleRef     = useRef("docTitle");
        this.autoSaveTimer = null;
        this._selectionTimer = null;
        this._selectionHandler = null;

        // Read params from action
        const params = this.props.action?.params || {};
        if (params.doc_id) {
            this.state.docId  = params.doc_id;
            this.state.title  = params.doc_name || "Untitled Document";
        }

        onWillStart(async () => {
            if (this.state.docId) {
                await this._loadDocument(this.state.docId);
            }
        });

        onMounted(() => {
            this._initEditor();
            this._setupSelectionTracking();
            this._startAutoSave();
        });

        onWillUnmount(() => {
            this._clearTimers();
        });
    }

    // ── Initialisation ────────────────────────────────────────────────────

    _initEditor() {
        const el = this.editorRef.el;
        if (!el) return;

        // Apply initial content if loaded
        if (this._pendingContent !== undefined) {
            el.innerHTML = this._pendingContent;
            delete this._pendingContent;
        }

        // Keyboard shortcuts
        el.addEventListener("keydown", (e) => {
            if (e.ctrlKey || e.metaKey) {
                switch (e.key.toLowerCase()) {
                    case "b": e.preventDefault(); this.execCmd("bold"); break;
                    case "i": e.preventDefault(); this.execCmd("italic"); break;
                    case "u": e.preventDefault(); this.execCmd("underline"); break;
                    case "s": e.preventDefault(); this.saveDocument(); break;
                    case "z": if (!e.shiftKey) { e.preventDefault(); this.execCmd("undo"); } break;
                    case "y": e.preventDefault(); this.execCmd("redo"); break;
                    case "a": e.preventDefault(); document.execCommand("selectAll"); break;
                    case "k": e.preventDefault(); this.state.showInsertLink = true; break;
                    case "f": e.preventDefault(); this.state.showFindReplace = !this.state.showFindReplace; break;
                }
            }
            // Tab = 4 spaces
            if (e.key === "Tab") {
                e.preventDefault();
                this.execCmd("insertHTML", "\u00a0\u00a0\u00a0\u00a0");
            }
        });

        // Track content changes
        el.addEventListener("input", () => {
            this.state.isDirty = true;
            this._updateStats();
        });

        el.addEventListener("paste", (e) => {
            e.preventDefault();
            const text = e.clipboardData.getData("text/html") ||
                         e.clipboardData.getData("text/plain") || "";
            this.execCmd("insertHTML", text);
        });

        el.focus();
        this._updateStats();
    }

    _setupSelectionTracking() {
        this._selectionHandler = () => {
            clearTimeout(this._selectionTimer);
            this._selectionTimer = setTimeout(() => this._syncToolbarState(), 60);
        };
        document.addEventListener("selectionchange", this._selectionHandler);
    }

    _syncToolbarState() {
        try {
            this.state.bold      = document.queryCommandState("bold");
            this.state.italic    = document.queryCommandState("italic");
            this.state.underline = document.queryCommandState("underline");
            this.state.strike    = document.queryCommandState("strikeThrough");
        } catch (_) {}
    }

    _startAutoSave() {
        this.autoSaveTimer = setInterval(async () => {
            if (this.state.isDirty && !this.state.isSaving) {
                await this._autoSave();
            }
        }, 3000);
    }

    _clearTimers() {
        if (this.autoSaveTimer)  clearInterval(this.autoSaveTimer);
        if (this._selectionTimer) clearTimeout(this._selectionTimer);
        if (this._selectionHandler) {
            document.removeEventListener("selectionchange", this._selectionHandler);
        }
    }

    // ── Document Load / Save ──────────────────────────────────────────────

    async _loadDocument(docId) {
        this.state.isLoading = true;
        try {
            const [doc] = await this.orm.read(
                "word.document",
                [docId],
                ["name", "content", "state", "tag_ids"]
            );
            this.state.title = doc.name;
            const el = this.editorRef.el;
            if (el) {
                el.innerHTML = doc.content || "<p><br></p>";
            } else {
                // Component not mounted yet — defer
                this._pendingContent = doc.content || "<p><br></p>";
            }
        } catch (err) {
            this.notification.add(_t("Could not load document."), { type: "danger" });
        }
        this.state.isLoading = false;
    }

    async _autoSave() {
        const content = this.editorRef.el ? this.editorRef.el.innerHTML : "";
        const name    = this.state.title;
        try {
            const result = await rpc("/word_editor/autosave", {
                doc_id:  this.state.docId,
                name,
                content,
            });
            if (result && result.doc_id) {
                this.state.docId = result.doc_id;
            }
            this.state.isDirty = false;
            this.state.savedAt = new Date();
        } catch (_) {}
    }

    async saveDocument() {
        if (this.state.isSaving) return;
        this.state.isSaving = true;
        const content = this.editorRef.el ? this.editorRef.el.innerHTML : "";
        try {
            if (this.state.docId) {
                await this.orm.write("word.document", [this.state.docId], {
                    name:    this.state.title,
                    content: content,
                });
            } else {
                const [id] = await this.orm.create("word.document", [{
                    name:    this.state.title || "Untitled Document",
                    content: content,
                }]);
                this.state.docId = id;
            }
            this.state.isDirty = false;
            this.state.savedAt = new Date();
            this.notification.add(_t("Document saved!"), { type: "success" });
        } catch (err) {
            this.notification.add(_t("Save failed. Please try again."), { type: "danger" });
        }
        this.state.isSaving = false;
    }

    // ── Navigation ────────────────────────────────────────────────────────

    async goBack() {
        if (this.state.isDirty) {
            await this._autoSave();
        }
        this.action.doAction("word_editor.action_word_document_manager");
    }

    // ── Core Editor Command ────────────────────────────────────────────────

    execCmd(command, value = null) {
        const el = this.editorRef.el;
        if (!el) return;
        el.focus();
        if (value !== null) {
            document.execCommand(command, false, value);
        } else {
            document.execCommand(command, false, null);
        }
        this.state.isDirty = true;
    }

    // ── Text Style ────────────────────────────────────────────────────────

    toggleBold()      { this.execCmd("bold"); }
    toggleItalic()    { this.execCmd("italic"); }
    toggleUnderline() { this.execCmd("underline"); }
    toggleStrike()    { this.execCmd("strikeThrough"); }
    toggleSuperscript(){ this.execCmd("superscript"); }
    toggleSubscript() { this.execCmd("subscript"); }
    clearFormat()     { this.execCmd("removeFormat"); }
    undo()            { this.execCmd("undo"); }
    redo()            { this.execCmd("redo"); }

    // ── Heading / Paragraph Style ─────────────────────────────────────────

    onHeadingChange(ev) {
        const tag = ev.target.value;
        this.state.currentHeading = tag;
        this.execCmd("formatBlock", tag);
    }

    // ── Font ─────────────────────────────────────────────────────────────

    onFontChange(ev) {
        const font = ev.target.value;
        this.state.currentFont = font;
        this.execCmd("fontName", font);
    }

    onSizeChange(ev) {
        const size = ev.target.value;
        this.state.currentSize = size;
        // execCommand fontSize only accepts 1-7; use custom span instead
        const sel = window.getSelection();
        if (sel && sel.toString().length > 0) {
            document.execCommand("fontSize", false, "7");
            const el = this.editorRef.el;
            if (el) {
                el.querySelectorAll("font[size='7']").forEach((f) => {
                    f.removeAttribute("size");
                    f.style.fontSize = `${size}pt`;
                    f.outerHTML = `<span style="font-size:${size}pt">${f.innerHTML}</span>`;
                });
            }
        }
    }

    // ── Alignment ────────────────────────────────────────────────────────

    alignLeft()    { this.execCmd("justifyLeft"); }
    alignCenter()  { this.execCmd("justifyCenter"); }
    alignRight()   { this.execCmd("justifyRight"); }
    alignJustify() { this.execCmd("justifyFull"); }

    // ── Lists ────────────────────────────────────────────────────────────

    bulletList()   { this.execCmd("insertUnorderedList"); }
    numberedList() { this.execCmd("insertOrderedList"); }
    indent()       { this.execCmd("indent"); }
    outdent()      { this.execCmd("outdent"); }

    // ── Colour Picker ─────────────────────────────────────────────────────

    openTextColorPicker() {
        this.state.colorPickerType = "text";
        this.state.showColorPicker = !this.state.showColorPicker;
    }

    openHiliteColorPicker() {
        this.state.colorPickerType = "hilite";
        this.state.showColorPicker = !this.state.showColorPicker;
    }

    applyColor(color) {
        if (this.state.colorPickerType === "text") {
            this.state.textColor = color;
            this.execCmd("foreColor", color);
        } else {
            this.state.hiliteColor = color;
            this.execCmd("hiliteColor", color);
        }
        this.state.showColorPicker = false;
    }

    // ── Table Insertion ───────────────────────────────────────────────────

    openTableModal() {
        this.state.showTableModal = true;
    }

    insertTable() {
        const rows = parseInt(this.state.tableRows) || 3;
        const cols = parseInt(this.state.tableCols) || 3;
        let html = `<table style="border-collapse:collapse;width:100%;margin:8px 0">`;
        for (let r = 0; r < rows; r++) {
            html += "<tr>";
            for (let c = 0; c < cols; c++) {
                const tag = r === 0 ? "th" : "td";
                html += `<${tag} style="border:1px solid #ccc;padding:8px 12px;min-width:60px">&nbsp;</${tag}>`;
            }
            html += "</tr>";
        }
        html += "</table><p><br></p>";
        this.execCmd("insertHTML", html);
        this.state.showTableModal = false;
    }

    // ── Link Insertion ────────────────────────────────────────────────────

    openInsertLink() {
        const sel = window.getSelection();
        this.state.linkText = sel ? sel.toString() : "";
        this.state.linkUrl  = "https://";
        this.state.showInsertLink = true;
    }

    confirmInsertLink() {
        const url = normalizeUrl(this.state.linkUrl);
        const text = this.state.linkText.trim() || url;
        if (url) {
            const html = `<a href="${escapeAttribute(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(text)}</a>`;
            this.execCmd("insertHTML", html);
        }
        this.state.showInsertLink = false;
    }

    // ── Image Insertion ───────────────────────────────────────────────────

    openInsertImage() {
        this.state.imageUrl = "";
        this.state.showInsertImage = true;
    }

    confirmInsertImage() {
        const url = normalizeUrl(this.state.imageUrl);
        if (url) {
            const html = `<img src="${escapeAttribute(url)}" alt="Image" style="max-width:100%;height:auto">`;
            this.execCmd("insertHTML", html);
        }
        this.state.showInsertImage = false;
    }

    insertHR() {
        this.execCmd("insertHTML", "<hr/><p><br></p>");
    }

    // ── Find & Replace ────────────────────────────────────────────────────

    findNext() {
        const term = this.state.findText;
        if (!term) return;
        const el = this.editorRef.el;
        if (!el) return;
        const text = el.innerHTML;
        const idx  = text.toLowerCase().indexOf(term.toLowerCase(),
                      this._lastFindIndex || 0);
        if (idx === -1) {
            this._lastFindIndex = 0;
            this.notification.add(_t("No more occurrences found."), { type: "info" });
        } else {
            this._lastFindIndex = idx + term.length;
        }
        window.find(term, false, false, true, false, true);
    }

    replaceNext() {
        const find    = this.state.findText;
        const replace = this.state.replaceText;
        if (!find) return;
        const sel = window.getSelection();
        if (sel && sel.toString().toLowerCase() === find.toLowerCase()) {
            this.execCmd("insertText", replace);
        }
        this.findNext();
    }

    replaceAll() {
        const find    = this.state.findText;
        const replace = this.state.replaceText;
        const el      = this.editorRef.el;
        if (!find || !el) return;
        const regex   = new RegExp(find.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
        el.innerHTML  = el.innerHTML.replace(regex, replace);
        this.state.isDirty = true;
        this._updateStats();
        this.notification.add(_t("Replacement complete."), { type: "success" });
    }

    // ── Templates ────────────────────────────────────────────────────────

    async openTemplates() {
        try {
            const tpls = await rpc("/word_editor/templates", {});
            this.state.templates   = tpls || [];
            this.state.showTemplates = true;
        } catch (_) {
            this.notification.add(_t("Could not load templates."), { type: "warning" });
        }
    }

    applyTemplate(tpl) {
        const el = this.editorRef.el;
        if (!el) return;
        el.innerHTML = tpl.content || "<p><br></p>";
        this.state.isDirty = true;
        this._updateStats();
        this.state.showTemplates = false;
    }

    applyBlankTemplate() {
        const el = this.editorRef.el;
        if (!el) return;
        el.innerHTML = "<p><br></p>";
        this.state.isDirty = true;
        this._updateStats();
        this.state.showTemplates = false;
    }

    // ── Page Break ───────────────────────────────────────────────────────

    insertPageBreak() {
        this.execCmd("insertHTML",
            `<div style="page-break-after:always;border-bottom:2px dashed #ccc;
              margin:16px 0;text-align:center;color:#aaa;font-size:11px;
              padding-bottom:4px">— Page Break —</div><p><br></p>`
        );
    }

    // ── Zoom ─────────────────────────────────────────────────────────────

    onZoomChange(ev) {
        this.state.zoom = parseInt(ev.target.value) || 100;
    }

    // ── Export / Print ────────────────────────────────────────────────────

    async exportDocx() {
        if (!this.state.docId || this.state.isDirty) {
            await this.saveDocument();
        }
        if (this.state.docId) {
            window.location.href = `/word_editor/export/docx/${this.state.docId}`;
        }
    }

    async exportPdf() {
        if (!this.state.docId || this.state.isDirty) {
            await this.saveDocument();
        }
        if (this.state.docId) {
            window.open(`/word_editor/export/pdf/${this.state.docId}`, "_blank");
        }
    }

    printDocument() {
        const el = this.editorRef.el;
        if (!el) return;
        const win = window.open("", "_blank", "width=900,height=700");
        win.document.write(`<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>${escapeHtml(this.state.title)}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: Arial, sans-serif; font-size: 12pt;
         line-height: 1.6; color: #000; padding: 2.54cm; }
  h1 { font-size: 22pt; margin-bottom: 6px; }
  h2 { font-size: 18pt; margin: 16px 0 6px; }
  h3 { font-size: 14pt; margin: 12px 0 6px; }
  p  { margin-bottom: 8px; }
  table { border-collapse: collapse; width: 100%; margin: 8px 0; }
  td, th { border: 1px solid #ccc; padding: 6px 10px; }
  th { background: #f5f5f5; font-weight: bold; }
  ul, ol { margin: 8px 0 8px 24px; }
  img { max-width: 100%; }
  @media print {
    body { padding: 0; }
    @page { margin: 2.54cm; }
  }
</style>
</head>
<body>
<h1 style="border-bottom:2px solid #333;padding-bottom:8px;margin-bottom:16px">
  ${escapeHtml(this.state.title)}
</h1>
${el.innerHTML}
</body>
</html>`);
        win.document.close();
        win.focus();
        setTimeout(() => { win.print(); win.close(); }, 500);
    }

    // ── Helpers ───────────────────────────────────────────────────────────

    _updateStats() {
        const el   = this.editorRef.el;
        const html = el ? el.innerHTML : "";
        const wc   = wordCount(html);
        const text = stripHtml(html);
        this.state.wordCount   = wc;
        this.state.charCount   = text.length;
        this.state.readingTime = Math.max(1, Math.round(wc / 200));
    }

    get savedAtLabel() {
        if (!this.state.savedAt) return "";
        const d = this.state.savedAt;
        return `${d.getHours().toString().padStart(2,"0")}:${d.getMinutes().toString().padStart(2,"0")}`;
    }

    get saveStatusLabel() {
        if (this.state.isSaving) return _t("Saving…");
        if (this.state.isDirty)  return _t("Unsaved changes");
        if (this.state.savedAt)  return _t("Saved at ") + this.savedAtLabel;
        return "";
    }

    get pageStyle() {
        return `transform: scale(${this.state.zoom / 100}); transform-origin: top center;`;
    }

    // Event helpers for two-way binding shims
    onTitleInput(ev)    { this.state.title       = ev.target.value; this.state.isDirty = true; }
    onFindInput(ev)     { this.state.findText    = ev.target.value; }
    onReplaceInput(ev)  { this.state.replaceText = ev.target.value; }
    onLinkUrlInput(ev)  { this.state.linkUrl     = ev.target.value; }
    onLinkTextInput(ev) { this.state.linkText    = ev.target.value; }
    onImageUrlInput(ev) { this.state.imageUrl    = ev.target.value; }
    onTableRows(ev)     { this.state.tableRows   = ev.target.value; }
    onTableCols(ev)     { this.state.tableCols   = ev.target.value; }

    closeAllModals() {
        this.state.showColorPicker  = false;
        this.state.showTableModal   = false;
        this.state.showInsertLink   = false;
        this.state.showInsertImage  = false;
        this.state.showFindReplace  = false;
        this.state.showTemplates    = false;
    }
}

// Odoo 19 action manager injects these extra props into every client action.
// Declaring them all stops OWL's strict prop validator from throwing.
WordEditorAction.props = {
    action:            { type: Object,          optional: true },
    actionId:          { type: [Number, String], optional: true },
    updateActionState: { type: Function,         optional: true },
    className:         { type: String,           optional: true },
};

// Register as client action
registry.category("actions").add("word_editor_action", WordEditorAction);

// ─── Export constants for template access ────────────────────────────────────
WordEditorAction.FONTS    = FONTS;
WordEditorAction.SIZES    = FONT_SIZES;
WordEditorAction.HEADINGS = HEADINGS;
WordEditorAction.COLORS   = COLORS;

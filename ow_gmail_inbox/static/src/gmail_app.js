/** @odoo-module **/
import { Component, onWillStart, onWillDestroy, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useSetupAction } from "@web/search/action_hook";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

const blankMessage = () => ({ to: "", cc: "", bcc: "", subject: "", body: "", attachments: [], reply_id: "" });
export class GmailWorkspace extends Component {
    static template = "ow_gmail_inbox.Workspace";
    static props = ["*"];
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.action = useService("action");
        this.state = useState({
            initializing: true, connected: false, configured: false, admin: false, email: "",
            messages: [], folder: "INBOX", query: "", appliedQuery: "", nextPage: "", pageToken: "", previous: [],
            loading: false, reading: false, selected: null, error: "", mutating: false,
            composing: false, draft: blankMessage(), sending: false, uploading: false, mobileNav: false,
        });
        this.folders = [
            { id: "INBOX", label: _t("Inbox"), icon: "fa-inbox" },
            { id: "STARRED", label: _t("Starred"), icon: "fa-star-o" },
            { id: "UNREAD", label: _t("Unread"), icon: "fa-envelope-o" },
            { id: "SENT", label: _t("Sent"), icon: "fa-paper-plane-o" },
            { id: "ALL", label: _t("All mail"), icon: "fa-archive" },
            { id: "TRASH", label: _t("Trash"), icon: "fa-trash-o" },
        ];
        this.listGeneration = 0;
        this.readGeneration = 0;
        this.alive = true;
        onWillStart(() => this.initialize());
        onWillDestroy(() => { this.alive = false; this.listGeneration++; this.readGeneration++; });
        useSetupAction({
            beforeLeave: () => this.beforeLeave(),
            beforeUnload: ev => {
                if (this.isDirty || this.state.sending || this.state.uploading) { ev.preventDefault(); ev.returnValue = ""; }
            },
        });
    }
    get folderName() { return this.folders.find(f => f.id === this.state.folder)?.label || _t("Inbox"); }
    get isDirty() {
        const d = this.state.draft;
        return this.state.composing && Boolean(d.to || d.cc || d.bcc || d.subject || d.body || d.attachments.length);
    }
    get pageNumber() { return this.state.previous.length + 1; }
    messageBody(message) {
        const body = typeof message?.body === "string" ? message.body.trim() : "";
        return body || _t("No text content. This message may contain only attachments.");
    }
    error(error) {
        if (!this.alive) return;
        this.state.error = error?.data?.message || error?.message || _t("The request could not be completed.");
    }
    call(method, args = []) { return this.orm.call("ow.gmail.account", method, args); }
    async initialize() {
        try {
            const status = await this.call("connection_status");
            Object.assign(this.state, status);
            if (status.connected) await this.load();
        } catch (error) { this.error(error); }
        finally { if (this.alive) this.state.initializing = false; }
    }
    async connect() { if (await this.beforeLeave()) window.location.assign("/ow_gmail/connect"); }
    settings() { return this.action.doAction("ow_gmail_inbox.action_gmail_settings"); }
    async load(token = "", previous = []) {
        const generation = ++this.listGeneration;
        ++this.readGeneration;
        this.state.reading = false;
        this.state.selected = null;
        this.state.loading = true;
        this.state.error = "";
        this.state.messages = [];
        try {
            const result = await this.call("list_messages", [this.state.folder, this.state.appliedQuery, token]);
            if (!this.alive || generation !== this.listGeneration) return;
            this.state.messages = result.messages;
            this.state.nextPage = result.next_page;
            this.state.pageToken = token;
            this.state.previous = previous;
        } catch (error) { if (generation === this.listGeneration) this.error(error); }
        finally { if (this.alive && generation === this.listGeneration) this.state.loading = false; }
    }
    folder(id) {
        this.state.folder = id;
        this.state.mobileNav = false;
        return this.load();
    }
    search() { this.state.appliedQuery = this.state.query.trim(); return this.load(); }
    next() { return this.load(this.state.nextPage, [...this.state.previous, this.state.pageToken]); }
    previous() {
        const stack = [...this.state.previous];
        return this.load(stack.pop() || "", stack);
    }
    refresh() { return this.load(this.state.pageToken, [...this.state.previous]); }
    async read(message) {
        if (this.state.composing && !await this.closeCompose()) return;
        const generation = ++this.readGeneration;
        this.state.reading = true;
        this.state.selected = null;
        this.state.error = "";
        try {
            const result = await this.call("read_message", [message.id]);
            if (!this.alive || generation !== this.readGeneration) return;
            this.state.selected = result;
            if (result.unread) {
                await this.call("modify_message", [message.id, "read"]);
                if (this.alive && generation === this.readGeneration) {
                    this.state.selected.unread = false;
                    const row = this.state.messages.find(item => item.id === message.id);
                    if (row) row.unread = false;
                }
            }
        } catch (error) { if (generation === this.readGeneration) this.error(error); }
        finally { if (this.alive && generation === this.readGeneration) this.state.reading = false; }
    }
    back() { this.state.selected = null; this.readGeneration++; this.state.reading = false; }
    async modify(message, operation) {
        if (this.state.mutating) return;
        if (operation === "trash" && !await this.confirm(_t("Move this message to Gmail Trash?"), _t("Move to Trash"))) return;
        this.state.mutating = true;
        this.state.error = "";
        try {
            await this.call("modify_message", [message.id, operation]);
            if (["archive", "trash", "untrash", "inbox"].includes(operation)) {
                await this.refresh();
            } else {
                const patch = operation === "star" || operation === "unstar" ? {starred: operation === "star"} : {unread: operation === "unread"};
                for (const item of this.state.messages.filter(item => item.id === message.id)) Object.assign(item, patch);
                if (this.state.selected?.id === message.id) Object.assign(this.state.selected, patch);
            }
        } catch (error) { this.error(error); }
        finally { if (this.alive) this.state.mutating = false; }
    }
    confirm(body, confirmLabel = _t("Continue")) {
        return new Promise(resolve => this.dialog.add(ConfirmationDialog, {
            title: _t("Gmail Inbox"), body, confirmLabel,
            confirm: () => resolve(true), cancel: () => resolve(false), dismiss: () => resolve(false),
        }));
    }
    async beforeLeave() {
        if (this.state.sending || this.state.uploading) return false;
        if (!this.isDirty) return true;
        if (!await this.confirm(_t("Discard this unsent message? Drafts are kept only while this app is open."), _t("Discard"))) return false;
        this.state.composing = false;
        this.state.draft = blankMessage();
        return true;
    }
    async compose(reply = null) {
        if (this.state.composing && !await this.closeCompose()) return;
        this.state.draft = blankMessage();
        if (reply) {
            this.state.draft.to = reply.reply_to || reply.sender;
            this.state.draft.subject = /^re:/i.test(reply.subject) ? reply.subject : "Re: " + reply.subject;
            this.state.draft.reply_id = reply.id;
        }
        this.state.composing = true;
        this.state.error = "";
    }
    async closeCompose() {
        if (!await this.beforeLeave()) return false;
        this.state.composing = false;
        this.state.draft = blankMessage();
        return true;
    }
    async attach(ev) {
        const files = [...(ev.target.files || [])];
        ev.target.value = "";
        const current = this.state.draft.attachments;
        if (current.length + files.length > 10 || current.reduce((n, f) => n + f.size, 0) + files.reduce((n, f) => n + f.size, 0) > 10 * 1024 * 1024) {
            this.state.error = _t("Attach up to ten files, totaling 10 MB or less."); return;
        }
        this.state.uploading = true;
        try {
            const items = await Promise.all(files.map(file => new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onerror = () => reject(new Error(_t("A selected file could not be read.")));
                reader.onload = () => resolve({ name: file.name, size: file.size, data: String(reader.result).split(",")[1] });
                reader.readAsDataURL(file);
            })));
            this.state.draft.attachments.push(...items);
        } catch (error) { this.error(error); }
        finally { if (this.alive) this.state.uploading = false; }
    }
    removeAttachment(index) { this.state.draft.attachments.splice(index, 1); }
    async send() {
        if (this.state.sending || this.state.uploading) return;
        this.state.sending = true;
        this.state.error = "";
        try {
            await this.call("send_message", [JSON.parse(JSON.stringify(this.state.draft))]);
            this.state.draft = blankMessage();
            this.state.composing = false;
            this.notification.add(_t("Message sent through Gmail."), {type: "success"});
            await this.refresh();
        } catch (error) { this.error(error); }
        finally { if (this.alive) this.state.sending = false; }
    }
    async disconnect(revoke = false) {
        if (!await this.beforeLeave()) return;
        const body = revoke ? _t("Revoke this app's Google access and remove your local connection? Google may also revoke other sessions using the same OAuth client.") : _t("Remove your Gmail connection from Odoo? You can reconnect later. Google-side access can be revoked from your Google account.");
        if (!await this.confirm(body, revoke ? _t("Revoke and disconnect") : _t("Disconnect"))) return;
        try {
            await this.call("disconnect", [revoke]);
            ++this.listGeneration; ++this.readGeneration;
            Object.assign(this.state, {connected:false,email:"",messages:[],selected:null,composing:false,draft:blankMessage(),error:"",loading:false,reading:false});
        } catch (error) { this.error(error); }
    }
    attachmentUrl(message, part) { return `/ow_gmail/attachment/${encodeURIComponent(message.id)}?part_id=${encodeURIComponent(part.part_id)}`; }
    size(bytes) { return bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`; }
    sender(value) { return value.replace(/<[^>]*>/g, "").replace(/"/g, "").trim() || value; }
}
registry.category("actions").add("ow_gmail_inbox.workspace", GmailWorkspace);

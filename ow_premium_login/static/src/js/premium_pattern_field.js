/** @odoo-module **/

import { Component, useRef, useState, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const NODES = Array.from({ length: 9 }, (_, index) => index);

export class PremiumPatternField extends Component {
    static template = xml`
        <div class="ow_backend_pattern_widget">
            <div class="ow_backend_pattern_heading">
                <span>Drag across 4 or more dots</span>
                <button type="button" t-on-click="clearPattern">Clear</button>
            </div>
            <div class="ow_pattern_lock" aria-label="Draw unlock pattern">
                <div class="ow_pattern_trace" t-att-class="{ 'has-pattern': state.pattern.length }">
                    <t t-if="state.pattern.length">
                        <t t-esc="patternDisplay"/>
                    </t>
                    <t t-else="">Connect 4 or more dots</t>
                </div>
                <div class="ow_pattern_grid" t-ref="grid"
                    t-on-pointermove="onPointerMove"
                    t-on-pointerup="onPointerUp"
                    t-on-pointercancel="onPointerUp"
                    t-on-lostpointercapture="onPointerUp">
                    <svg class="ow_pattern_lines" aria-hidden="true" focusable="false">
                        <polyline t-ref="line" points=""/>
                    </svg>
                    <t t-foreach="nodes" t-as="node" t-key="node">
                        <button type="button"
                            t-att-data-node="node"
                            t-att-class="{ 'is-selected': isSelected(node) }"
                            t-att-aria-label="'Pattern dot ' + (node + 1)"
                            t-att-disabled="props.readonly"
                            t-on-pointerdown="onPointerDown"
                            t-on-click="onNodeClick">
                            <t t-if="isSelected(node)" t-esc="nodeOrder(node)"/>
                        </button>
                    </t>
                </div>
            </div>
            <div class="ow_backend_pattern_value" t-if="state.pattern.length">
                Pattern saved on user record: <strong><t t-esc="patternValue"/></strong>
            </div>
        </div>`;

    static props = { ...standardFieldProps };

    setup() {
        this.nodes = NODES;
        this.grid = useRef("grid");
        this.line = useRef("line");
        this.state = useState({ pattern: this.parsePattern(this.props.record.data[this.props.name]) });
        this.drawing = false;
        this.pointerId = null;
    }

    parsePattern(value) {
        const valid = new Set(NODES.map(String));
        return String(value || '')
            .split('-')
            .filter((node, index, values) => valid.has(node) && values.indexOf(node) === index);
    }

    isSelected(node) {
        return this.state.pattern.includes(String(node));
    }

    nodeOrder(node) {
        return this.state.pattern.indexOf(String(node)) + 1;
    }

    get patternDisplay() {
        return this.state.pattern.map((node) => Number(node) + 1).join('  ›  ');
    }

    get patternValue() {
        // Keep the Security tab preview consistent with the visible dot
        // labels. The server still receives the internal 0-8 node IDs.
        return this.patternDisplay;
    }

    updateValue() {
        this.props.record.update({ [this.props.name]: this.state.pattern.join('-') });
        window.requestAnimationFrame(() => this.updateLine());
    }

    updateLine() {
        if (!this.grid.el || !this.line.el) {
            return;
        }
        const gridBox = this.grid.el.getBoundingClientRect();
        const points = this.state.pattern.map((value) => {
            const node = this.grid.el.querySelector(`[data-node="${value}"]`);
            if (!node) {
                return '';
            }
            const nodeBox = node.getBoundingClientRect();
            return `${nodeBox.left - gridBox.left + nodeBox.width / 2},${nodeBox.top - gridBox.top + nodeBox.height / 2}`;
        }).filter(Boolean).join(' ');
        this.line.el.setAttribute('points', points);
    }

    nodeAtPoint(event) {
        const element = document.elementFromPoint(event.clientX, event.clientY);
        const node = element && element.closest('[data-node]');
        return node && this.grid.el.contains(node) ? node : null;
    }

    addNode(node) {
        if (this.props.readonly || !node || this.state.pattern.length >= 9) {
            return;
        }
        const value = node.dataset.node;
        if (this.state.pattern.includes(value)) {
            return;
        }

        const last = this.state.pattern.length ? Number(this.state.pattern[this.state.pattern.length - 1]) : null;
        const current = Number(value);
        if (last !== null) {
            const lastRow = Math.floor(last / 3);
            const lastColumn = last % 3;
            const currentRow = Math.floor(current / 3);
            const currentColumn = current % 3;
            const middleRow = (lastRow + currentRow) / 2;
            const middleColumn = (lastColumn + currentColumn) / 2;
            if (Number.isInteger(middleRow) && Number.isInteger(middleColumn)) {
                const middle = String(middleRow * 3 + middleColumn);
                if (!this.state.pattern.includes(middle) && middle !== value) {
                    this.state.pattern.push(middle);
                }
            }
        }
        this.state.pattern.push(value);
        this.updateValue();
    }

    onPointerDown(event) {
        const node = event.currentTarget;
        if (this.props.readonly || !node.dataset.node) {
            return;
        }
        event.preventDefault();
        event.stopPropagation();
        this.drawing = true;
        this.pointerId = event.pointerId;
        this.grid.el.setPointerCapture?.(event.pointerId);
        this.addNode(node);
    }

    onPointerMove(event) {
        if (!this.drawing || event.pointerId !== this.pointerId) {
            return;
        }
        event.preventDefault();
        this.addNode(this.nodeAtPoint(event));
    }

    onPointerUp(event) {
        if (event.pointerId === this.pointerId) {
            this.drawing = false;
            this.pointerId = null;
        }
    }

    onNodeClick(event) {
        if (!this.drawing && event.currentTarget.dataset.node) {
            this.addNode(event.currentTarget);
        }
    }

    clearPattern() {
        this.state.pattern.splice(0, this.state.pattern.length);
        this.updateValue();
    }
}

export const premiumPatternField = {
    component: PremiumPatternField,
    displayName: "Premium Unlock Pattern",
    supportedTypes: ["char"],
};

registry.category("fields").add("premium_pattern", premiumPatternField);

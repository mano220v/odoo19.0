/** @odoo-module **/

/* Premium login uses plain DOM APIs on purpose: the login page must remain
 * usable before the full Odoo web client has booted. */

(() => {
    const modes = ['password', 'pin', 'pattern', 'text_lock'];

    function initPremiumLogin(form) {
        if (form.dataset.owPremiumLoginReady === '1') {
            return;
        }
        form.dataset.owPremiumLoginReady = '1';
        const authentication = form.querySelector('.ow_premium_authentication');
        const typeInput = form.querySelector('#login_type, input[name="type"]');
        if (!authentication) {
            return;
        }

        // Keep the login contract valid even if another inherited view has
        // replaced Odoo's original hidden type input.
        const credentialType = typeInput || Object.assign(document.createElement('input'), {
            type: 'hidden',
            name: 'type',
            id: 'login_type',
            value: 'password',
        });
        if (!typeInput) {
            form.appendChild(credentialType);
        }

        const panels = [...authentication.querySelectorAll('[data-login-panel]')];
        const modeButtons = [...authentication.querySelectorAll('[data-login-mode-button]')];
        const pattern = [];
        const patternGrid = authentication.querySelector('.ow_pattern_grid');
        const patternLine = authentication.querySelector('[data-pattern-line]');
        let drawingPattern = false;
        let activePointerId = null;

        const fields = {
            password: form.querySelector('#password'),
            pin: form.querySelector('#login_pin'),
            pattern: form.querySelector('#login_pattern'),
            text_lock: form.querySelector('#login_text_lock'),
        };

        function activeMode() {
            return authentication.dataset.loginMode || 'password';
        }

        function syncCredentialField() {
            const mode = activeMode();
            modes.forEach((name) => {
                const field = fields[name];
                if (!field) {
                    return;
                }
                field.removeAttribute('name');
                field.removeAttribute('required');
            });
            if (fields[mode]) {
                fields[mode].name = 'password';
                fields[mode].required = true;
            }
            credentialType.value = mode;
        }

        function setMode(mode) {
            if (!modes.includes(mode)) {
                return;
            }
            authentication.dataset.loginMode = mode;
            modeButtons.forEach((button) => {
                const selected = button.dataset.loginModeButton === mode;
                button.classList.toggle('is-active', selected);
                button.setAttribute('aria-selected', selected ? 'true' : 'false');
            });
            panels.forEach((panel) => {
                const selected = panel.dataset.loginPanel === mode;
                panel.classList.toggle('is-active', selected);
                panel.hidden = !selected;
            });
            syncCredentialField();
            if (fields[mode]) {
                window.setTimeout(() => fields[mode].focus(), 20);
            }
        }

        function toggleSecret(button) {
            const field = form.querySelector(`#${button.dataset.toggleSecret}`);
            if (!field) {
                return;
            }
            const visible = field.type === 'text';
            field.type = visible ? 'password' : 'text';
            button.setAttribute('aria-label', `${visible ? 'Show' : 'Hide'} ${button.dataset.toggleSecret}`);
            const icon = button.querySelector('i');
            if (icon) {
                icon.classList.toggle('fa-eye', visible);
                icon.classList.toggle('fa-eye-slash', !visible);
            }
        }

        function updatePattern() {
            if (fields.pattern) {
                fields.pattern.value = pattern.join('-');
            }
            const trace = authentication.querySelector('[data-pattern-trace]');
            if (trace) {
                trace.textContent = pattern.length ? pattern.map((node) => Number(node) + 1).join('  ›  ') : 'Connect 4 or more dots';
                trace.classList.toggle('has-pattern', pattern.length > 0);
            }
            authentication.querySelectorAll('[data-pattern-node]').forEach((node) => {
                const selected = pattern.includes(node.dataset.patternNode);
                node.classList.toggle('is-selected', selected);
                node.textContent = selected ? String(pattern.indexOf(node.dataset.patternNode) + 1) : '';
            });

            if (patternLine && patternGrid) {
                const gridBox = patternGrid.getBoundingClientRect();
                const points = pattern.map((value) => {
                    const node = patternGrid.querySelector(`[data-pattern-node="${value}"]`);
                    if (!node) {
                        return '';
                    }
                    const nodeBox = node.getBoundingClientRect();
                    return `${nodeBox.left - gridBox.left + nodeBox.width / 2},${nodeBox.top - gridBox.top + nodeBox.height / 2}`;
                }).filter(Boolean).join(' ');
                patternLine.setAttribute('points', points);
            }
        }

        function nodeAtPoint(clientX, clientY) {
            if (!patternGrid) {
                return null;
            }
            const element = document.elementFromPoint(clientX, clientY);
            const node = element && element.closest('[data-pattern-node]');
            return node && patternGrid.contains(node) ? node : null;
        }

        function addPatternNode(node) {
            if (!node || pattern.length >= 9) {
                return;
            }
            const value = node.dataset.patternNode;
            if (pattern.includes(value)) {
                return;
            }

            // Android-style patterns automatically include the centre node
            // when a gesture passes directly through it.
            const last = pattern.length ? Number(pattern[pattern.length - 1]) : null;
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
                    if (!pattern.includes(middle) && middle !== value) {
                        const middleNode = patternGrid.querySelector(`[data-pattern-node="${middle}"]`);
                        if (middleNode) {
                            pattern.push(middle);
                        }
                    }
                }
            }
            pattern.push(value);
            updatePattern();
        }

        form.addEventListener('click', (event) => {
            const button = event.target.closest('[data-login-mode-button]');
            if (button && form.contains(button)) {
                event.preventDefault();
                setMode(button.dataset.loginModeButton);
            }
        });

        authentication.querySelectorAll('[data-toggle-secret]').forEach((button) => {
            button.addEventListener('click', () => toggleSecret(button));
        });

        authentication.querySelectorAll('[data-pin-key]').forEach((button) => {
            button.addEventListener('click', () => {
                const field = fields.pin;
                if (!field || field.value.length >= 8) {
                    return;
                }
                field.value += button.dataset.pinKey;
                field.dispatchEvent(new Event('input', {bubbles: true}));
            });
        });

        const backspace = authentication.querySelector('[data-pin-action="backspace"]');
        if (backspace) {
            backspace.addEventListener('click', () => {
                if (fields.pin) {
                    fields.pin.value = fields.pin.value.slice(0, -1);
                    fields.pin.focus();
                }
            });
        }

        if (patternGrid) {
            patternGrid.addEventListener('pointerdown', (event) => {
                const node = nodeAtPoint(event.clientX, event.clientY);
                if (!node) {
                    return;
                }
                event.preventDefault();
                drawingPattern = true;
                activePointerId = event.pointerId;
                patternGrid.setPointerCapture?.(event.pointerId);
                addPatternNode(node);
            });
            patternGrid.addEventListener('pointermove', (event) => {
                if (!drawingPattern || event.pointerId !== activePointerId) {
                    return;
                }
                event.preventDefault();
                addPatternNode(nodeAtPoint(event.clientX, event.clientY));
            });
            const stopPattern = (event) => {
                if (event.pointerId === activePointerId) {
                    drawingPattern = false;
                    activePointerId = null;
                }
            };
            patternGrid.addEventListener('pointerup', stopPattern);
            patternGrid.addEventListener('pointercancel', stopPattern);
            patternGrid.addEventListener('lostpointercapture', stopPattern);
            // Keyboard users can still build a pattern one dot at a time.
            patternGrid.querySelectorAll('[data-pattern-node]').forEach((node) => {
                node.addEventListener('click', () => {
                    if (!drawingPattern) {
                        addPatternNode(node);
                    }
                });
            });
            window.addEventListener('resize', updatePattern);
        }

        const patternReset = authentication.querySelector('[data-pattern-reset]');
        if (patternReset) {
            patternReset.addEventListener('click', () => {
                pattern.splice(0, pattern.length);
                updatePattern();
            });
        }

        const clearUser = form.querySelector('[data-clear-login]');
        if (clearUser) {
            clearUser.addEventListener('click', (event) => {
                event.preventDefault();
                const login = form.querySelector('#login');
                if (login) {
                    login.value = '';
                    login.focus();
                }
            });
        }

        form.addEventListener('submit', (event) => {
            syncCredentialField();
            const mode = activeMode();
            const value = fields[mode] ? fields[mode].value : '';
            if (mode === 'pin' && !/^\d{4,8}$/.test(value)) {
                event.preventDefault();
                fields.pin.setCustomValidity('Enter a PIN with 4 to 8 digits.');
                fields.pin.reportValidity();
                fields.pin.setCustomValidity('');
                return;
            }
            if (mode === 'pattern' && pattern.length < 4) {
                event.preventDefault();
                window.alert('Connect at least 4 dots to create your unlock pattern.');
                return;
            }
            if (mode === 'text_lock' && value.trim().length < 4) {
                event.preventDefault();
                fields.text_lock.setCustomValidity('Enter at least 4 characters.');
                fields.text_lock.reportValidity();
                fields.text_lock.setCustomValidity('');
                return;
            }
            const submit = form.querySelector('button[type="submit"]');
            if (submit) {
                submit.classList.add('is-authenticating');
                submit.setAttribute('aria-busy', 'true');
            }
        });

        syncCredentialField();
        updatePattern();
    }

    function boot() {
        document.querySelectorAll('form.ow_premium_login_form, form.oe_login_form, form[action^="/web/login"]').forEach(initPremiumLogin);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot, {once: true});
    } else {
        boot();
    }
    window.addEventListener('load', boot, {once: true});
    window.setTimeout(boot, 50);
})();

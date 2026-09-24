/** @odoo-module **/

/**
 * A dependency-free, safe arithmetic/scientific expression evaluator.
 * Deliberately does NOT use eval()/Function() - expressions are tokenized
 * and evaluated through a shunting-yard parser instead.
 */

function toRad(deg) {
    return (deg * Math.PI) / 180;
}
function toDeg(rad) {
    return (rad * 180) / Math.PI;
}
function factorial(n) {
    if (n < 0 || Math.floor(n) !== n) {
        throw new Error("Factorial is only defined for non-negative integers");
    }
    let result = 1;
    for (let i = 2; i <= n; i++) {
        result *= i;
    }
    return result;
}

const FUNCTIONS = {
    sin: (x) => Math.sin(toRad(x)),
    cos: (x) => Math.cos(toRad(x)),
    tan: (x) => Math.tan(toRad(x)),
    asin: (x) => toDeg(Math.asin(x)),
    acos: (x) => toDeg(Math.acos(x)),
    atan: (x) => toDeg(Math.atan(x)),
    log: (x) => Math.log10(x),
    ln: (x) => Math.log(x),
    sqrt: (x) => Math.sqrt(x),
    abs: (x) => Math.abs(x),
    exp: (x) => Math.exp(x),
};

const CONSTANTS = {
    pi: Math.PI,
    e: Math.E,
};

const PRECEDENCE = { "+": 1, "-": 1, "*": 2, "/": 2, "%": 2, "^": 3 };
const RIGHT_ASSOC = { "^": true };

function tokenize(expression) {
    const tokens = [];
    const src = expression.replace(/\s+/g, "");
    let i = 0;
    while (i < src.length) {
        const char = src[i];
        if (/[0-9.]/.test(char)) {
            let num = char;
            i++;
            while (i < src.length && /[0-9.]/.test(src[i])) {
                num += src[i];
                i++;
            }
            tokens.push({ type: "number", value: parseFloat(num) });
            continue;
        }
        if (/[a-zA-Z]/.test(char)) {
            let ident = char;
            i++;
            while (i < src.length && /[a-zA-Z]/.test(src[i])) {
                ident += src[i];
                i++;
            }
            tokens.push({ type: "identifier", value: ident });
            continue;
        }
        if ("+-*/^%!()".includes(char)) {
            tokens.push({ type: "operator", value: char });
            i++;
            continue;
        }
        throw new Error(`Unexpected character: ${char}`);
    }
    return tokens;
}

function isUnaryContext(prevToken) {
    if (!prevToken) {
        return true;
    }
    if (prevToken.type === "operator" && prevToken.value !== ")" && prevToken.value !== "!") {
        return true;
    }
    return false;
}

function toPostfix(tokens) {
    const output = [];
    const stack = [];
    let prevToken = null;

    for (const token of tokens) {
        if (token.type === "number") {
            output.push(token);
        } else if (token.type === "identifier") {
            if (CONSTANTS[token.value] !== undefined) {
                output.push({ type: "number", value: CONSTANTS[token.value] });
            } else if (FUNCTIONS[token.value]) {
                stack.push({ type: "function", value: token.value });
            } else {
                throw new Error(`Unknown identifier: ${token.value}`);
            }
        } else if (token.value === "(") {
            stack.push(token);
        } else if (token.value === ")") {
            while (stack.length && stack[stack.length - 1].value !== "(") {
                output.push(stack.pop());
            }
            stack.pop(); // discard "("
            if (stack.length && stack[stack.length - 1].type === "function") {
                output.push(stack.pop());
            }
        } else if (token.value === "!") {
            output.push({ type: "postfix", value: "!" });
        } else if (token.value === "-" && isUnaryContext(prevToken)) {
            stack.push({ type: "operator", value: "neg" });
        } else {
            while (
                stack.length &&
                stack[stack.length - 1].type === "operator" &&
                stack[stack.length - 1].value !== "(" &&
                stack[stack.length - 1].value !== "neg" &&
                (PRECEDENCE[stack[stack.length - 1].value] > PRECEDENCE[token.value] ||
                    (PRECEDENCE[stack[stack.length - 1].value] === PRECEDENCE[token.value] &&
                        !RIGHT_ASSOC[token.value]))
            ) {
                output.push(stack.pop());
            }
            stack.push(token);
        }
        prevToken = token;
    }
    while (stack.length) {
        const top = stack.pop();
        if (top.value === "(") {
            throw new Error("Mismatched parentheses");
        }
        output.push(top);
    }
    return output;
}

function evaluatePostfix(postfix) {
    const stack = [];
    for (const token of postfix) {
        if (token.type === "number") {
            stack.push(token.value);
        } else if (token.type === "function") {
            const arg = stack.pop();
            stack.push(FUNCTIONS[token.value](arg));
        } else if (token.type === "postfix" && token.value === "!") {
            stack.push(factorial(stack.pop()));
        } else if (token.value === "neg") {
            stack.push(-stack.pop());
        } else {
            const b = stack.pop();
            const a = stack.pop();
            switch (token.value) {
                case "+":
                    stack.push(a + b);
                    break;
                case "-":
                    stack.push(a - b);
                    break;
                case "*":
                    stack.push(a * b);
                    break;
                case "/":
                    if (b === 0) {
                        throw new Error("Division by zero");
                    }
                    stack.push(a / b);
                    break;
                case "%":
                    stack.push(a % b);
                    break;
                case "^":
                    stack.push(Math.pow(a, b));
                    break;
                default:
                    throw new Error(`Unknown operator: ${token.value}`);
            }
        }
    }
    if (stack.length !== 1) {
        throw new Error("Invalid expression");
    }
    return stack[0];
}

/**
 * Evaluate a math expression string (e.g. "3+4*sin(30)") and return a number.
 * Throws a plain Error with a user-readable message on invalid input.
 */
export function evaluateExpression(expression) {
    if (!expression || !expression.trim()) {
        return 0;
    }
    const tokens = tokenize(expression);
    const postfix = toPostfix(tokens);
    const result = evaluatePostfix(postfix);
    if (!isFinite(result)) {
        throw new Error("Result is not a finite number");
    }
    return result;
}

/** Round a number to a fixed number of decimals, trimming trailing zeros. */
export function roundResult(value, precision = 4) {
    const factor = Math.pow(10, precision);
    const rounded = Math.round(value * factor) / factor;
    return rounded;
}

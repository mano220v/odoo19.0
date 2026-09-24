/** @odoo-module **/

/**
 * Unit categories for the Unit Converter tool. Every category (except
 * temperature, which is non-linear) stores a factor to convert 1 unit
 * into the category's base unit.
 */
export const UNIT_CATEGORIES = {
    length: {
        label: "Length",
        units: { mm: 0.001, cm: 0.01, m: 1, km: 1000, in: 0.0254, ft: 0.3048, yd: 0.9144, mi: 1609.344 },
    },
    weight: {
        label: "Weight",
        units: { mg: 0.000001, g: 0.001, kg: 1, t: 1000, oz: 0.0283495, lb: 0.453592 },
    },
    temperature: {
        label: "Temperature",
        units: { c: "Celsius", f: "Fahrenheit", k: "Kelvin" },
    },
    area: {
        label: "Area",
        units: { sqm: 1, sqkm: 1000000, sqft: 0.092903, sqyd: 0.836127, acre: 4046.86, hectare: 10000 },
    },
    volume: {
        label: "Volume",
        units: { ml: 0.001, l: 1, m3: 1000, gal: 3.78541, cup: 0.24, floz: 0.0295735 },
    },
    speed: {
        label: "Speed",
        units: { mps: 1, kmph: 0.277778, mph: 0.44704, knot: 0.514444 },
    },
    time: {
        label: "Time",
        units: { s: 1, min: 60, hr: 3600, day: 86400, week: 604800 },
    },
    data: {
        label: "Digital Storage",
        units: { kb: 0.0009765625, mb: 1, gb: 1024, tb: 1048576 },
    },
};

function convertTemperature(from, to, value) {
    let celsius;
    if (from === "c") {
        celsius = value;
    } else if (from === "f") {
        celsius = ((value - 32) * 5) / 9;
    } else {
        celsius = value - 273.15;
    }
    if (to === "c") {
        return celsius;
    } else if (to === "f") {
        return (celsius * 9) / 5 + 32;
    }
    return celsius + 273.15;
}

/** Convert `value` from `fromUnit` to `toUnit` within `category`. */
export function convertUnit(category, fromUnit, toUnit, value) {
    if (category === "temperature") {
        return convertTemperature(fromUnit, toUnit, value);
    }
    const def = UNIT_CATEGORIES[category];
    const baseValue = value * def.units[fromUnit];
    return baseValue / def.units[toUnit];
}

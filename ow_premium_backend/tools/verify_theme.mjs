// Run with node tools/verify_theme.mjs. No Odoo server or npm install required.
import fs from 'node:fs';
import assert from 'node:assert/strict';
const source = name => fs.readFileSync(new URL('../static/src/js/' + name, import.meta.url), 'utf8');
const pure = source('theme_preferences.js');
const { DEFAULTS, PALETTES, normalizePreferences, normalizeProfiles, parseTheme, serializeTheme, resolvePalette, luminance } = await import('data:text/javascript;base64,' + Buffer.from(pure).toString('base64'));
for (const value of [null, undefined, 42, false, 'invalid', [], {}]) assert.deepEqual(normalizePreferences(value), DEFAULTS);
assert.deepEqual(normalizePreferences({palette:'invalid',customPrimary:'url(x)',fontFamily:'external',depth:NaN,glow:'1'}), DEFAULTS);
assert.equal(normalizePreferences({depth:1000,glow:-5}).depth,100);
assert.equal(normalizePreferences({depth:1000,glow:-5}).glow,0);
const old = normalizePreferences({palette:'ruby',mode:'dark',motion:false});
assert.equal(old.palette,'ruby');assert.equal(old.inputStyle,'soft');assert.equal(old.motion,false);
for (const palette of PALETTES) {
    const colors=resolvePalette({palette:palette.id});
    assert.ok(1.05/(luminance(colors.color)+0.05)>=4.5);
    assert.ok(1.05/(luminance(colors.secondary)+0.05)>=4.5);
}
for (const customPrimary of ['#ffffff','#ffff00','#000000','#00ff00','#ff00ff']) {
    const colors=resolvePalette({customColors:true,customPrimary});
    assert.ok(1.05/(luminance(colors.color)+0.05)>=4.5);
}
assert.deepEqual(parseTheme(serializeTheme(old)),old);
for (const invalid of ['{','null','{}','{"format":"ow-premium-backend","version":99,"preferences":{}}','x'.repeat(20001)]) assert.throws(()=>parseTheme(invalid));
assert.equal(normalizeProfiles([{id:'one',name:'Theme',preferences:{}},{id:'one',name:'Duplicate',preferences:{}},{id:'<bad>',name:'Bad',preferences:{}}]).length,1);
assert.equal(normalizeProfiles(Array.from({length:20},(_,i)=>({id:'t'+i,name:'x'.repeat(100),preferences:{}}))).length,8);
const entries=new Map(), storage=new Map(), events={};
const root={dataset:{},classList:{toggle:(k,v)=>entries.set(k,v)},style:{setProperty:(k,v)=>entries.set(k,v)}};
globalThis.document={documentElement:root};
const media={matches:false,addEventListener:(k,v)=>events.media=v};
globalThis.window={matchMedia:()=>media};
const key='ow_premium_backend:v1:test:4';
storage.set(key,JSON.stringify({palette:'ruby',mode:'dark'}));
let failStorage=false;
globalThis.owTest={reactive:x=>x,registry:{category:()=>({add:(k,v)=>entries.set(k,v)})},session:{db:'test',uid:4},browser:{localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>{if(failStorage)throw new Error('quota');storage.set(k,v)}},addEventListener:(k,v)=>events[k]=v}};
const serviceSource=source('appearance_service.js').replace(/^import .*;$/gm,'');
await import('data:text/javascript;base64,'+Buffer.from('const {reactive,registry,session,browser}=globalThis.owTest;\n'+pure+'\n'+serviceSource).toString('base64'));
const service=entries.get('ow_appearance').start();
assert.equal(service.state.palette,'ruby');
service.update({customColors:true,customPrimary:'#ffffff',formWidth:'wide',inputStyle:'outlined'});
assert.equal(root.dataset.owInputStyle,'outlined');assert.equal(root.dataset.owFormWidth,'wide');
assert.equal(service.library.undoCount,1);service.undo();assert.equal(service.state.customColors,false);
service.update({mode:'system'});media.matches=true;events.media();assert.equal(root.dataset.owMode,'dark');
assert.equal(service.saveProfile(' '),'name');
for(let i=0;i<8;i++)assert.equal(service.saveProfile('Look '+i),null);
assert.equal(service.saveProfile('ninth'),'limit');
assert.equal(service.library.profiles.length,8);
service.removeProfile(service.library.profiles[0].id);assert.equal(service.library.profiles.length,7);
const snapshot=serializeTheme(service.state);assert.throws(()=>service.importTheme('bad'));assert.equal(serializeTheme(service.state),snapshot);
service.update({enabled:false});assert.equal(entries.get('ow-premium'),false);
service.importTheme(snapshot);assert.equal(entries.get('ow-premium'),true);
for(let i=0;i<25;i++)service.update({depth:i});assert.equal(service.library.undoCount,20);
storage.set(key,JSON.stringify({palette:'teal',tableStyle:'tinted'}));events.storage({key});assert.equal(service.state.palette,'teal');assert.equal(service.library.undoCount,0);
storage.delete(key);events.storage({key:null});assert.deepEqual(service.state,DEFAULTS);
failStorage=true;service.update({mode:'dark'});assert.equal(service.library.persistent,false);assert.equal(service.state.mode,'dark');
console.log('Passed: migration, validation, palette contrast, import/export, profiles, history, system mode, persistence, cross-tab changes and storage failure.');

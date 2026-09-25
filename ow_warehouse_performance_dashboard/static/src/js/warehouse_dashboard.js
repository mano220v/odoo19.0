/** @odoo-module **/
import { Component, onWillStart, onWillUnmount, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { useService } from "@web/core/utils/hooks";

export class WarehouseOpsCenter extends Component {
    static template = "ow_warehouse_performance_dashboard.Dashboard";
    static components = { Layout };
    setup() {
        this.orm=useService("orm"); this.action=useService("action");
        this.state=useState({period:"week",loading:true,error:false,updated:"",data:{
            kpi:{open:0,due24:0,overdue:0,ready:0,waiting:0,incoming:0,outgoing:0,completed:0,onTime:0,batches:null,reorder:0},
            domains:{},aging:{under24:0,under48:0,over48:0},workload:[],queue:[],trend:[],reorders:[]}});
        onWillStart(()=>this.reload());
        this.timer=setInterval(()=>this.reload(false),60000);
        onWillUnmount(()=>clearInterval(this.timer));
    }
    now(){return new Date();}
    dt(date){return date.toISOString().slice(0,19).replace("T"," ");}
    periodStart(){
        const d=this.now();
        if(this.state.period==="today")d.setHours(0,0,0,0);
        else if(this.state.period==="week"){d.setDate(d.getDate()-(d.getDay()+6)%7);d.setHours(0,0,0,0);}
        else if(this.state.period==="month"){d.setDate(1);d.setHours(0,0,0,0);}
        else return null;
        return this.dt(d);
    }
    periodEnd(){
        const d=this.now();
        if(this.state.period==="today"){d.setHours(0,0,0,0);d.setDate(d.getDate()+1);}
        else if(this.state.period==="week"){const offset=(d.getDay()+6)%7;d.setDate(d.getDate()-offset+7);d.setHours(0,0,0,0);}
        else if(this.state.period==="month"){d.setDate(1);d.setMonth(d.getMonth()+1);d.setHours(0,0,0,0);}
        else return null;
        return this.dt(d);
    }
    async count(model,domain){try{return await this.orm.searchCount(model,domain);}catch{return 0;}}
    async reload(spinner=true){
        if(spinner)this.state.loading=true;
        this.state.error=false;
        try{
            const start=this.periodStart(),end=this.periodEnd(),nowText=this.dt(this.now()),tomorrow=this.dt(new Date(Date.now()+86400000));
            const ago24=this.dt(new Date(Date.now()-86400000)),ago48=this.dt(new Date(Date.now()-172800000));
            const baseOpen=[["state","not in",["done","cancel"]]];
            const open=[...baseOpen];
            if(start)open.push(["scheduled_date",">=",start]);
            if(end)open.push(["scheduled_date","<",end]);
            const overdue=[["state","not in",["done","cancel"]],["scheduled_date","<",nowText]];
            const ageDomains={
                under24:[...overdue,["scheduled_date",">=",ago24]],
                under48:[...overdue,["scheduled_date","<",ago24],["scheduled_date",">=",ago48]],
                over48:[...overdue,["scheduled_date","<",ago48]],
            };
            const due24=[...baseOpen,["scheduled_date",">=",nowText],["scheduled_date","<",tomorrow]];
            const ready=[...open,["state","=","assigned"]];
            const waiting=[...open,["state","in",["confirmed","waiting"]]];
            const incoming=[...open,["picking_type_code","=","incoming"]];
            const outgoing=[...open,["picking_type_code","=","outgoing"]];
            const done=[["state","=","done"]];
            if(start)done.push(["date_done",">=",start]);
            if(end)done.push(["date_done","<",end]);
            const doneOutbound=[...done,["picking_type_code","=","outgoing"]];
            const [nOpen,nDue,nLate,nReady,nWaiting,nIn,nOut,nDone,slaRows]=await Promise.all([
                this.count("stock.picking",open),this.count("stock.picking",due24),this.count("stock.picking",overdue),
                this.count("stock.picking",ready),this.count("stock.picking",waiting),this.count("stock.picking",incoming),
                this.count("stock.picking",outgoing),this.count("stock.picking",done),
                this.orm.searchRead("stock.picking",doneOutbound,["scheduled_date","date_done"],{limit:5000}).catch(()=>[])
            ]);
            let ontime=0,measurable=0;
            for(const r of slaRows){if(r.scheduled_date&&r.date_done){measurable++;if(r.date_done<=r.scheduled_date)ontime++;}}
            const [queueRows,ageRows,types,trendRows,reorderRows,nReorder]=await Promise.all([
                this.orm.searchRead("stock.picking",[["state","not in",["done","cancel"]],["scheduled_date","!=",false]],["name","state","scheduled_date","picking_type_code","picking_type_id","partner_id"],{order:"scheduled_date asc,id asc",limit:1000}),
                this.orm.searchRead("stock.picking",overdue,["scheduled_date"],{limit:10000}).catch(()=>[]),
                this.orm.searchRead("stock.picking.type",[],["name","code"],{limit:80}).catch(()=>[]),
                this.loadTrendRows(),
                this.orm.searchRead("stock.warehouse.orderpoint",[["qty_to_order",">",0]],["product_id","qty_to_order"],{order:"qty_to_order desc,id",limit:6}).catch(()=>[]),
                this.count("stock.warehouse.orderpoint",[["qty_to_order",">",0]])
            ]);
            const ageHours=ageRows.map(r=>Math.max(0,(this.now()-new Date(r.scheduled_date.replace(" ","T")+"Z"))/3600000));
            const aging={under24:ageHours.filter(h=>h<24).length,under48:ageHours.filter(h=>h>=24&&h<48).length,over48:ageHours.filter(h=>h>=48).length};
            const queue=queueRows.slice(0,8).map(r=>{
                const due=new Date(r.scheduled_date.replace(" ","T")+"Z").getTime();
                return {id:r.id,name:r.name||"Transfer",operation:r.picking_type_id?r.picking_type_id[1]:"Warehouse operation",code:r.picking_type_code||"",partner:r.partner_id?r.partner_id[1]:"—",scheduled:r.scheduled_date,late:due<this.now().getTime(),age:this.age(r.scheduled_date)};
            });
            const workload=await Promise.all(types.slice(0,10).map(async t=>({id:t.id,name:t.name,code:t.code,count:await this.count("stock.picking",[...open,["picking_type_id","=",t.id]])})));
            let batches=null;
            try{batches=await this.orm.searchCount("stock.picking.batch",[["state","not in",["done","cancel"]]]);}catch{/* Optional batch transfers. */}
            this.state.data={
                kpi:{open:nOpen,due24:nDue,overdue:nLate,ready:nReady,waiting:nWaiting,incoming:nIn,outgoing:nOut,completed:nDone,onTime:measurable?Math.round(ontime*100/measurable):0,batches,reorder:nReorder},
                domains:{open,due24,overdue,ready,waiting,incoming,outgoing,done,doneOutbound,reorder:[["qty_to_order",">",0]],...ageDomains},
                aging,workload:workload.filter(x=>x.count).sort((a,b)=>b.count-a.count).slice(0,6),
                queue,trend:this.makeTrend(trendRows),
                reorders:reorderRows.map(r=>({id:r.id,product:r.product_id?r.product_id[1]:"Product",qty:r.qty_to_order}))
            };
            this.state.updated=new Date().toLocaleTimeString();
        }catch(e){this.state.error=true;}finally{this.state.loading=false;}
    }
    async loadTrendRows(){
        const d=this.now();d.setHours(0,0,0,0);d.setDate(d.getDate()-13);
        return this.orm.searchRead("stock.picking",[["state","=","done"],["date_done",">=",this.dt(d)]],["date_done","picking_type_code"],{order:"date_done asc",limit:10000}).catch(()=>[]);
    }
    makeTrend(rows){
        const days=[],today=this.now();today.setHours(0,0,0,0);
        for(let i=13;i>=0;i--){const d=new Date(today);d.setDate(d.getDate()-i);days.push({key:d.toISOString().slice(0,10),label:d.toLocaleDateString(undefined,{day:"numeric",month:"short"}),incoming:0,outgoing:0,internal:0});}
        const byKey=Object.fromEntries(days.map(d=>[d.key,d]));
        for(const r of rows){if(r.date_done&&byKey[r.date_done.slice(0,10)]&&["incoming","outgoing","internal"].includes(r.picking_type_code))byKey[r.date_done.slice(0,10)][r.picking_type_code]++;}
        return days;
    }
    age(value){
        const h=(this.now()-new Date(value.replace(" ","T")+"Z"))/3600000;
        if(h<0){const ahead=Math.abs(h);return ahead<24?"in "+Math.ceil(ahead)+"h":"in "+Math.ceil(ahead/24)+"d";}
        return h<24?Math.floor(h)+"h late":Math.floor(h/24)+"d late";
    }
    maxTrend(){return Math.max(1,...this.state.data.trend.map(d=>d.incoming+d.outgoing+d.internal));}
    barHeight(v){return Math.max(v?5:0,Math.round(v/this.maxTrend()*100));}
    maxWorkload(){return Math.max(1,...this.state.data.workload.map(x=>x.count));}
    workloadWidth(v){return Math.max(4,Math.round(v/this.maxWorkload()*100));}
    async setPeriod(period){this.state.period=period;await this.reload();}
    open(model,domain,name,views){this.action.doAction({type:"ir.actions.act_window",name,res_model:model,views:views||[[false,"list"],[false,"form"]],domain:domain||[],target:"current"});}
    openTransfers(domain,name){this.open("stock.picking",domain,name);}
    openReplenishment(){this.open("stock.warehouse.orderpoint",this.state.data.domains.reorder,"Replenishment");}
    openTransfer(id){this.action.doAction({type:"ir.actions.act_window",res_model:"stock.picking",res_id:id,views:[[false,"form"]],target:"current"});}
    async createOperation(code){const names={incoming:"Receipt",outgoing:"Delivery",internal:"Internal Transfer"};const types=await this.orm.searchRead("stock.picking.type",[["code","=",code]],["id"],{limit:1}).catch(()=>[]);const context=types.length?{default_picking_type_id:types[0].id}:{};this.action.doAction({type:"ir.actions.act_window",name:"New "+names[code],res_model:"stock.picking",views:[[false,"form"]],target:"current",context});}
}
registry.category("actions").add("ow_warehouse_performance_dashboard_tag",WarehouseOpsCenter);
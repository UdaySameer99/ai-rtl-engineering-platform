const $ = id => document.getElementById(id);
let mode = "generate";
const examples = {
rtl: `module counter4 (\n    input  wire       clk,\n    input  wire       rst_n,\n    output reg  [3:0] count\n);\n    always @(posedge clk or negedge rst_n) begin\n        if (!rst_n)\n            count <= 4'd0;\n        else\n            count <= count + 1'b1;\n    end\nendmodule`,
tb: `module tb_counter4;\n    reg clk = 0;\n    reg rst_n = 0;\n    wire [3:0] count;\n    counter4 dut (.clk(clk), .rst_n(rst_n), .count(count));\n    always #5 clk = ~clk;\n    initial begin\n        #12; rst_n = 1;\n        repeat (5) begin\n            @(posedge clk); #1;\n        end\n        if (count !== 4'd5) $fatal(1, "FAIL: expected 5, got %0d", count);\n        $display("PASS: counter reached 5");\n        $finish;\n    end\nendmodule`
};
const panels = {
generate: ["01","Generate RTL","Generate RTL","Generate RTL","prompt"],
review: ["02","Review & detect bugs","Review RTL","Review RTL","code"],
fix: ["03","Correct RTL","Fix RTL","Fix RTL","code"],
testbench: ["04","Generate testbench","Generate testbench","Generate testbench","prompt"]
};
function setMode(next) {
 mode=next; const p=panels[next];
 document.querySelectorAll(".nav").forEach(b=>b.classList.toggle("active",b.dataset.panel===next));
 $("stepLabel").textContent="WORKFLOW / "+p[0]; $("panelTitle").textContent=p[1]; $("runAI").innerHTML=p[2]+" <span>→</span>";
 $("promptWrap").classList.toggle("hidden", next==="review" || next==="fix");
 $("codeWrap").classList.toggle("hidden", next==="generate");
 $("tbWrap").classList.toggle("hidden", next==="generate");
 $("resultSection").classList.add("hidden"); $("error").classList.add("hidden");
}
document.querySelectorAll(".nav").forEach(b=>b.addEventListener("click",()=>setMode(b.dataset.panel)));
$("loadExample").onclick=()=>{$("rtl").value=examples.rtl};
$("loadTb").onclick=()=>{$("testbench").value=examples.tb};
$("clear").onclick=()=>{["prompt","rtl","testbench","resultText"].forEach(id=>$(id).value="");$("resultSection").classList.add("hidden");$("error").classList.add("hidden");$("simResult").classList.add("hidden")};
function showError(message){$("error").textContent=message;$("error").classList.remove("hidden")}
$("runAI").onclick=async()=>{
 $("error").classList.add("hidden");$("resultSection").classList.add("hidden");
 $("busy").classList.remove("hidden");$("busyText").textContent="Contacting cloud AI…";$("runAI").disabled=true;
 try{
  const r=await fetch("/api/ai",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({mode,prompt:$("prompt").value,code:$("rtl").value,testbench:$("testbench").value})});
  const d=await r.json();if(!r.ok)throw new Error(d.error||"AI request failed.");
  $("resultText").textContent=d.result;$("resultSection").classList.remove("hidden");
 }catch(e){showError(e.message)}finally{$("busy").classList.add("hidden");$("runAI").disabled=false}
};
$("copyResult").onclick=async()=>{try{await navigator.clipboard.writeText($("resultText").textContent);$("copyResult").textContent="COPIED"}catch(e){$("copyResult").textContent="COPY UNAVAILABLE"}};
$("useResult").onclick=()=>{
 const t=$("resultText").textContent;
 const match=t.match(/(?:RTL_CODE|CORRECTED_CODE)\s*:\s*([\s\S]*?)(?=\n(?:TESTBENCH|ASSUMPTIONS|TEST_RECOMMENDATIONS|SUMMARY|FINDINGS|DESIGN_NOTES)\s*:|$)/i);
 $("rtl").value=match?match[1].trim():t;
 $("codeWrap").classList.remove("hidden");$("resultSection").classList.add("hidden");
};
$("simulate").onclick=async()=>{
 $("simResult").classList.add("hidden");$("simBusy").classList.remove("hidden");$("simulate").disabled=true;
 try{
  const r=await fetch("/api/simulate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({code:$("rtl").value,testbench:$("testbench").value,top:$("top").value})});
  const d=await r.json();if(!r.ok && !d.status)throw new Error(d.error||"Simulation request failed.");
  let html="";
  if(d.error) html+=`<div class="simstatus fail">${escapeHtml(d.status||"ERROR")}: ${escapeHtml(d.error)}</div>`;
  else html+=`<div class="simstatus ${d.status==="passed"?"pass":"fail"}">${escapeHtml(d.status.toUpperCase())} · ${d.duration}s</div>`;
  if(d.compile_output)html+=`<h4>COMPILER OUTPUT</h4><pre>${escapeHtml(d.compile_output)}</pre>`;
  if(d.simulation_output)html+=`<h4>SIMULATION OUTPUT</h4><pre>${escapeHtml(d.simulation_output)}</pre>`;
  if(!d.compile_output&&!d.simulation_output&&!d.error)html+="<p>No output was produced.</p>";
  $("simResult").innerHTML=html;$("simResult").classList.remove("hidden");
 }catch(e){showError(e.message)}finally{$("simBusy").classList.add("hidden");$("simulate").disabled=false}
};
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
async function health(){
 try{const r=await fetch("/api/health");const d=await r.json();const good=d.status==="online"&&d.compiler_available&&d.simulator_available;
 $("healthText").textContent=good?(d.ai_configured?"Cloud AI + HDL simulator online":"HDL simulator online · AI key missing"):"Some cloud services unavailable";
 document.querySelector(".status-dot").style.background=good?"#b8e15a":"#e3b85d";
 }catch(e){$("healthText").textContent="Cloud connection unavailable"}
}
health();

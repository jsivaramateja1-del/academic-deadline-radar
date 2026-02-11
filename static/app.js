const p=document.getElementById("pass");
const s=document.getElementById("strength");

if(p){
p.addEventListener("input",()=>{
let l=p.value.length;
if(l<4) s.innerText="Weak";
else if(l<7) s.innerText="Medium";
else s.innerText="Strong";
});
}

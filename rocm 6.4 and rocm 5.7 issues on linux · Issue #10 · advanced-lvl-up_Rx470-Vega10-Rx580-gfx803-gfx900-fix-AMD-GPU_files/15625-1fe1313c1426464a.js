performance.mark("js-parse-end:15625-1fe1313c1426464a.js");
"use strict";(globalThis.webpackChunk_github_ui_github_ui=globalThis.webpackChunk_github_ui_github_ui||[]).push([["15625"],{261828(e,t,r){r.r(t),r.d(t,{markdownEnrichmentSuccess:()=>l,showMarkdownRenderError:()=>s});var n=r(906997),a=r(221403),i=r(821744),o=r(159836);let d=new WeakMap;function l(e){let t=e.closest(".js-render-needs-enrichment");t&&(t.classList.remove("render-error"),d.get(t)?.setLoading(!1))}function s(e,t){let r=e.closest(".js-render-needs-enrichment");return!!r&&(r.classList.add("render-error"),r.querySelector(".js-render-block-actions")?.remove(),d.get(r)?.setError(!0,t))}function c(e,t,r){let a=r.identifier??"",i=new URL(e,window.location.origin);for(let[e,r]of Object.entries(t))i.searchParams.append(e,`${r}`);return i.hash=a,(0,n.qy)`
    <div
      class="render-container color-bg-transparent js-render-target p-0"
      data-identity="${a}"
      data-host="${i.origin}"
      data-type="${r.type}"
    >
      <iframe
        title="File display"
        role="presentation"
        class="render-viewer"
        src="${String(i)}"
        name="${a}"
        data-content="${r.contentJson}"
        sandbox="allow-scripts allow-same-origin allow-top-navigation allow-popups"
      >
      </iframe>
    </div>
  `}(0,a.lB)(".js-render-needs-enrichment",{constructor:HTMLElement,initialize:function(e){var t,r;let a,i,l={color_mode:(0,o.PT)()},s=e.getAttribute("data-type"),u=e.getAttribute("data-src"),h=e.getAttribute("data-identity"),p=e.getElementsByClassName("js-render-enrichment-target")[0],m=e.getElementsByClassName("js-render-enrichment-loader")[0],g=p.closest("details"),y=document.createElement("div");y.classList.add("js-render-enrichment-fallback"),e.appendChild(y);let f=p.firstElementChild;y.appendChild(f);let v={setLoading(e){m.hidden=!e},setError:(e,t)=>(v.setLoading(!1),!1!==e&&(f.classList.toggle("render-plaintext-hidden",!e),!!t&&((0,n.XX)([t,f],y),!0)))};d.set(e,v);let b=p.getAttribute("data-plain"),w=p.getAttribute("data-json");if(null==w||null==b)throw v.setError(!0,(0,n.qy)`<p class="flash flash-error">Unable to render rich display</p>`),Error(`Expected to see input data for type: ${s}`);let k=c(u,l,{type:s,identifier:h,contentJson:w}),L=c(u,l,{type:s,identifier:`${h}-fullscreen`,contentJson:w}),_=(t=()=>{(0,n.XX)(L,p.getElementsByClassName("Box-body")[0])},r={type:s},a=(0,n.qy)`<clipboard-copy
    aria-label="Copy ${r.type} code"
    .value=${b}
    class="btn my-2 js-clipboard-copy p-0 d-inline-flex tooltipped-no-delay"
    role="button"
    data-copy-feedback="Copied!"
    data-tooltip-direction="s"
  >
    <svg
      aria-hidden="true"
      height="16"
      viewBox="0 0 16 16"
      version="1.1"
      width="16"
      class="octicon octicon-copy js-clipboard-copy-icon m-2"
    >
      <path
        fill-rule="evenodd"
        d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 010 1.5h-1.5a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 00.25-.25v-1.5a.75.75 0 011.5 0v1.5A1.75 1.75 0 019.25 16h-7.5A1.75 1.75 0 010 14.25v-7.5z"
      ></path>
      <path
        fill-rule="evenodd"
        d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0114.25 11h-7.5A1.75 1.75 0 015 9.25v-7.5zm1.75-.25a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 00.25-.25v-7.5a.25.25 0 00-.25-.25h-7.5z"
      ></path>
    </svg>
    <svg
      aria-hidden="true"
      height="16"
      viewBox="0 0 16 16"
      version="1.1"
      width="16"
      class="octicon octicon-check js-clipboard-check-icon color-fg-success d-none m-2"
    >
      <path
        fill-rule="evenodd"
        d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z"
      ></path>
    </svg>
  </clipboard-copy>`,i=(0,n.qy)`
    <details class="details-reset details-overlay details-overlay-dark" style="display: contents">
      <summary
        role="button"
        aria-label="Open dialog"
        class="btn my-2 mr-2 p-0 d-inline-flex"
        aria-haspopup="dialog"
        @click="${t}"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" class="octicon m-2">
          <path
            fill-rule="evenodd"
            d="M3.72 3.72a.75.75 0 011.06 1.06L2.56 7h10.88l-2.22-2.22a.75.75 0 011.06-1.06l3.5 3.5a.75.75 0 010 1.06l-3.5 3.5a.75.75 0 11-1.06-1.06l2.22-2.22H2.56l2.22 2.22a.75.75 0 11-1.06 1.06l-3.5-3.5a.75.75 0 010-1.06l3.5-3.5z"
          ></path>
        </svg>
      </summary>
      <details-dialog
        class="Box Box--overlay render-full-screen d-flex flex-column anim-fade-in fast"
        aria-label="${r.type} rendered container"
      >
        <div>
          <button
            aria-label="Close dialog"
            data-close-dialog=""
            type="button"
            data-view-component="true"
            class="Link--muted btn-link position-absolute render-full-screen-close"
          >
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="currentColor"
              style="display:inline-block;vertical-align:text-bottom"
              class="octicon octicon-x"
            >
              <path
                fill-rule="evenodd"
                d="M5.72 5.72a.75.75 0 011.06 0L12 10.94l5.22-5.22a.75.75 0 111.06 1.06L13.06 12l5.22 5.22a.75.75 0 11-1.06 1.06L12 13.06l-5.22 5.22a.75.75 0 01-1.06-1.06L10.94 12 5.72 6.78a.75.75 0 010-1.06z"
              ></path>
            </svg>
          </button>
          <div class="Box-body border-0" role="presentation"></div>
        </div>
      </details-dialog>
    </details>
  `,(0,n.qy)`<div
    class="js-render-block-actions position-absolute top-0 pr-2 right-0 d-flex flex-justify-end flex-items-center"
  >
    ${i}${a}
  </div>`);g&&!g.open?g.addEventListener("toggle",()=>{g.open&&(0,n.XX)([_,k],p)},{once:!0}):(0,n.XX)([_,k],p)}}),(0,i.on)("preview:toggle:off",".js-previewable-comment-form",function(e){let t=e.currentTarget.querySelector(".js-render-needs-enrichment"),r=t?.querySelector(".js-render-enrichment-target");r&&(r.textContent="")}),(0,i.on)("preview:rendered",".js-previewable-comment-form",function(e){let t=e.currentTarget.querySelector(".js-render-needs-enrichment");t&&d.get(t)?.setLoading(!1)})},767440(e,t,r){r.r(t),r.d(t,{collapseAllInContainer:()=>v,expandAllInContainer:()=>f,handleMessage:()=>y,supportsRichExpanding:()=>d});var n=r(906997),a=r(261828),i=r(221403),o=r(101433);function d(e){return!!e.querySelector('.js-render-target[data-type="ipynb"]')}let l=["is-render-pending","is-render-ready","is-render-loading","is-render-loaded"],s=["is-render-ready","is-render-loading","is-render-loaded","is-render-failed","is-render-failed-fatally"],c=new WeakMap;function u(e){let t=c.get(e);null!=t&&(t.load=t.hello=null,t.helloTimer&&(clearTimeout(t.helloTimer),t.helloTimer=null),t.loadTimer&&(clearTimeout(t.loadTimer),t.loadTimer=null))}function h(e,t=""){var r,i;let o;e.classList.remove(...l),e.classList.add("is-render-failed");let d=function(e){let t=(0,n.qy)`<p>Unable to render rich display</p>`;if(""!==e){let r=e.split("\n");t=(0,n.qy)`<p><b>Unable to render rich display</b></p>
      <p>${r.map(e=>(0,n.qy)`${e}<br />`)}</p>`}return(0,n.qy)`<div class="flash flash-error">${t}</div>`}(t);!1===(0,a.showMarkdownRenderError)(e,d)&&(r=e,i=d,(o=r.querySelector(".render-viewer-error"))&&(o.remove(),r.classList.remove("render-container"),(0,n.XX)(i,r))),u(e)}function p(e,t=!1){!(!e||!(0,o.A)(e)||e.classList.contains("is-render-ready")||e.classList.contains("is-render-failed")||e.classList.contains("is-render-failed-fatally"))&&(!t||c.get(e)?.hello)&&h(e)}function m(e,t,r){return!!e&&!!e.postMessage&&(e.postMessage(JSON.stringify(t),r),!0)}function g(e){return t=>{if(!t.querySelector(".js-render-target"))return;let r=t.querySelector("iframe"),n=r?.contentWindow;if(n)return e(n)}}function y(e){let t=e.data;if(!t)return;if("string"==typeof t)try{t=JSON.parse(t)}catch{return}if("object"!=typeof t&&void 0!=t||"render"!==t.type||"string"!=typeof t.identity)return;let r=t.identity;if("string"!=typeof t.body)return;let n=t.body,i=function(e,t){for(let r of e.querySelectorAll(".js-render-target[data-identity][data-host]"))if(r.getAttribute("data-identity")===t)return r;return null}(document,r);if(!i||e.origin!==i.getAttribute("data-host"))return;let o=e.origin,d=null!=t.payload?t.payload:void 0,s=i.querySelector("iframe"),u=s?.contentWindow;switch(n){case"hello":if((c.get(i)||{untimed:!0}).hello=Date.now(),!u)return;m(u,{type:"render:cmd",body:{cmd:"ack",ack:!0}},o),m(u,{type:"render:cmd",body:{cmd:"branding",branding:!1}},o);break;case"error":h(i,d?.error);break;case"error:fatal":h(i,d?.error),i.classList.add("is-render-failed-fatal");break;case"error:invalid":h(i,d?.error),i.classList.add("is-render-failed-invalid");break;case"loading":i.classList.remove(...l),i.classList.add("is-render-loading");break;case"loaded":i.classList.remove(...l),i.classList.add("is-render-loaded");break;case"ready":(0,a.markdownEnrichmentSuccess)(i),i.classList.remove(...l),i.classList.add("is-render-ready"),d&&"number"==typeof d.height&&(i.style.height=`${d.height}px`,""!==location.hash&&window.dispatchEvent(new HashChangeEvent("hashchange"))),d?.ack===!0&&window.requestAnimationFrame(()=>{setTimeout(()=>{m(u,{type:"render:cmd",body:{cmd:"code_rendering_service:ready:ack","code_rendering_service:ready:ack":{}}},o)},0)});break;case"resize":d&&"number"==typeof d.height&&(i.style.height=`${d.height}px`);break;case"code_rendering_service:container:get_size":m(u,{type:"render:cmd",body:{cmd:"code_rendering_service:container:size","code_rendering_service:container:size":{width:i?.getBoundingClientRect().width}}},o);break;case"code_rendering_service:markdown:get_data":let p;if(!u)return;let g=s?.getAttribute("data-content")??"";try{p=JSON.parse(g)?.data}catch{p=null}p&&m(u,{type:"render:cmd",body:{cmd:"code_rendering_service:data:ready","code_rendering_service:data:ready":{data:p,width:i?.getBoundingClientRect().width}}},o)}}(0,i.lB)(".js-render-target",function(e){e.classList.remove(...s),e.style.height="auto",c.get(e)?.load||(u(e),c.get(e)||(c.set(e,{load:Date.now(),hello:null,helloTimer:window.setTimeout(p,1e4,e,!0),loadTimer:window.setTimeout(p,45e3,e)}),e.classList.add("is-render-automatic","is-render-requested")))}),window.addEventListener("message",y);let f=g(e=>m(e,{type:"render:cmd",body:{cmd:"code_rendering_service:behaviour:expand_all"}},origin)),v=g(e=>m(e,{type:"render:cmd",body:{cmd:"code_rendering_service:behaviour:collapse_all"}},origin))},159836(e,t,r){r.d(t,{OQ:()=>o,PA:()=>l,PT:()=>u,Px:()=>s,to:()=>c});var n=r(401289),a=r(17005);function i(){(0,a.TV)("preferred_color_mode",o())}function o(){return d("dark")?"dark":d("light")?"light":void 0}function d(e){return window.matchMedia&&window.matchMedia(`(prefers-color-scheme: ${e})`).matches}function l(e){let t=document.querySelector("html[data-color-mode]");t&&t.setAttribute("data-color-mode",e)}function s(e,t){let r=document.querySelector("html[data-color-mode]");r&&r.setAttribute(`data-${t}-theme`,e)}function c(e){let t=document.querySelector("html[data-color-mode]");if(t)return t.getAttribute(`data-${e}-theme`)}function u(e="light"){let t=function(){let e=document.querySelector("html[data-color-mode]");if(e)return e.getAttribute("data-color-mode")}();return("auto"===t?o():t)??e}(async()=>{if(await n.G,i(),window.matchMedia){let e=window.matchMedia("(prefers-color-scheme: dark)");e?.addEventListener?e.addEventListener("change",i):e.addListener(i)}})()},101433(e,t,r){r.d(t,{A:()=>n});function n(e){return!(e.offsetWidth<=0&&e.offsetHeight<=0)}}}]);
//# sourceMappingURL=15625-1fe1313c1426464a-8110603c60d02cd3.js.map
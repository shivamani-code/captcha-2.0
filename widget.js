(function () {
  'use strict';

  function onReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  function getSelfSrc() {
    var cs = document.currentScript;
    if (cs && cs.src) return cs.src;
    var scripts = document.getElementsByTagName('script');
    for (var i = scripts.length - 1; i >= 0; i--) {
      if (scripts[i] && scripts[i].src && /\/widget\.js(\?|#|$)/.test(scripts[i].src)) return scripts[i].src;
    }
    return '';
  }

  function resolveAssetUrl(assetPath) {
    try {
      var base = getSelfSrc();
      if (!base) return assetPath;
      var u = new URL(base);
      return u.origin + assetPath;
    } catch (_) {
      return assetPath;
    }
  }

  onReady(function () {
    var mount = document.getElementById('smartcaptcha');
    if (!mount) return;

    var cssUrl = resolveAssetUrl('/style.css?v=2');
    var jsUrl = resolveAssetUrl('/smartcaptcha.js?v=3');
    var fbUrl = resolveAssetUrl('/firebaseFeedback.js?v=2');
    var fbModalUrl = resolveAssetUrl('/feedbackModal.js?v=2');

    mount.innerHTML = '';

    var token = String(Math.random()).slice(2) + String(Date.now());

    var iframe = document.createElement('iframe');
    iframe.title = 'SmartCAPTCHA';
    iframe.setAttribute('scrolling', 'no');
    iframe.style.border = '0';
    iframe.style.width = '100%';
    iframe.style.height = '420px';
    iframe.style.display = 'block';

    function onMsg(e) {
      try {
        if (!e || e.source !== iframe.contentWindow) return;
        var d = e.data;
        if (!d || d.__scw_token !== token || d.__scw_type !== 'resize') return;
        var h = Number(d.h);
        if (!isFinite(h) || h <= 0) return;
        iframe.style.height = Math.max(220, Math.min(1200, Math.ceil(h))) + 'px';
      } catch (_) {
      }
    }
    window.addEventListener('message', onMsg);

    var doc = '';
    doc += '<!doctype html>';
    doc += '<html lang="en">';
    doc += '<head>';
    doc += '<meta charset="utf-8" />';
    doc += '<meta name="viewport" content="width=device-width, initial-scale=1" />';
    doc += '<link rel="stylesheet" href="' + cssUrl + '" />';
    doc += '<style>';
    doc += 'html,body{margin:0;padding:0;}';
    doc += '.sc-embed{min-height:1px;}';
    doc += '</style>';
    doc += '</head>';
    doc += '<body>';
    doc += '<div class="sc-embed">';
    doc += '<main class="page">';
    doc += '<h1 class="title">SmartCAPTCHA</h1>';
    doc += '<p class="subtitle">Complete the slider. The widget will send behavioral features to the deployed verifier service.</p>';
    doc += '<section id="smartcaptcha-root" class="captcha-root"></section>';
    doc += '<section class="result">';
    doc += '<div id="smartcaptcha-status" class="status" aria-live="polite"></div>';
    doc += '<div class="actions">';
    doc += '<button id="smartcaptcha-reset" class="btn" type="button">Reset</button>';
    doc += '</div>';
    doc += '</section>';
    doc += '</main>';
    doc += '<footer class="sc-footer">';
    doc += '<a id="smartcaptcha-feedback" class="sc-footer-link" href="#">Feedback</a>';
    doc += '</footer>';
    doc += '<div id="sc-feedback-modal" class="sc-modal" hidden>';
    doc += '<div class="sc-modal__backdrop" data-sc-close="true"></div>';
    doc += '<div class="sc-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="sc-feedback-title">';
    doc += '<button type="button" class="sc-modal__close" data-sc-close="true" aria-label="Close">×</button>';
    doc += '<h2 id="sc-feedback-title" class="sc-modal__title">Feedback</h2>';
    doc += '<form id="sc-feedback-form" class="sc-modal__form">';
    doc += '<label class="sc-modal__label">';
    doc += '<span>Email *</span>';
    doc += '<input id="sc-feedback-email" class="sc-modal__input" type="email" required autocomplete="email" />';
    doc += '</label>';
    doc += '<label class="sc-modal__label">';
    doc += '<span>Message</span>';
    doc += '<textarea id="sc-feedback-message" class="sc-modal__textarea" rows="4"></textarea>';
    doc += '</label>';
    doc += '<div id="sc-feedback-status" class="sc-modal__status" aria-live="polite"></div>';
    doc += '<div class="sc-modal__actions">';
    doc += '<button id="sc-feedback-submit" class="btn" type="submit">Send</button>';
    doc += '</div>';
    doc += '</form>';
    doc += '</div>';
    doc += '</div>';
    doc += '</div>';
    doc += '<script>';
    doc += '(function(){';
    doc += 'var T="' + token + '";';
    doc += 'function send(){try{var h=Math.max(document.documentElement.scrollHeight,document.body.scrollHeight);parent.postMessage({__scw_type:"resize",__scw_token:T,h:h},"*");}catch(_){}}';
    doc += 'window.addEventListener("load",send);window.addEventListener("resize",send);';
    doc += 'new MutationObserver(send).observe(document.documentElement,{subtree:true,childList:true,attributes:true,characterData:true});';
    doc += 'setInterval(send,800);';
    doc += '})();';
    doc += '<\/script>';
    doc += '<script>';
    doc += '(function(){';
    doc += 'function safePost(payload){try{window.parent&&window.parent.postMessage&&window.parent.postMessage(payload,"*");}catch(_){}}';
    doc += 'function genToken(){try{if(window.crypto&&window.crypto.getRandomValues){var a=new Uint8Array(16);window.crypto.getRandomValues(a);var s="";for(var i=0;i<a.length;i++){s+=a[i].toString(16).padStart(2,"0");}return s;} }catch(_){};return (String(Math.random()).slice(2)+String(Date.now()));}';
    doc += 'var sentOk=false;var sentFail=false;';
    doc += 'function check(){try{var el=document.getElementById("smartcaptcha-status");if(!el)return;var t=(el.textContent||"").trim();';
    doc += 'if(t.indexOf("Verified: Human")===0&&!sentOk){sentOk=true;sentFail=false;var tok=window.__SMARTCAPTCHA_WIDGET_VERIFICATION_TOKEN__||"";if(!tok){tok=genToken();window.__SMARTCAPTCHA_WIDGET_VERIFICATION_TOKEN__=tok;}safePost({type:"SMARTCAPTCHA_VERIFIED",success:true,token:String(tok)});}';
    doc += 'if(t.indexOf("Verification failed.")===0&&!sentFail){sentFail=true;sentOk=false;safePost({type:"SMARTCAPTCHA_FAILED",success:false});}';
    doc += 'if(t===""||t==="Try again."||t==="Verifying..."||t.indexOf("Try again.")!==-1){sentFail=false;}';
    doc += '}catch(_){}}';
    doc += 'function start(){try{check();var el=document.getElementById("smartcaptcha-status");if(!el)return;new MutationObserver(check).observe(el,{subtree:true,childList:true,characterData:true});}catch(_){}}';
    doc += 'if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",start);}else{start();}';
    doc += '})();';
    doc += '<\/script>';
    doc += '<script src="' + jsUrl + '"><\/script>';
    doc += '<script src="' + fbUrl + '"><\/script>';
    doc += '<script src="' + fbModalUrl + '"><\/script>';
    doc += '</body>';
    doc += '</html>';

    iframe.srcdoc = doc;
    mount.appendChild(iframe);
  });
})();

// SPDX-License-Identifier: Apache-2.0 AND MIT
// Copyright (c) 2026 Fenolite contributors
// The script of the Fenolite viewer page, built by viewer/build.mjs from viewer/src (change c0304). Do not edit:
// change the sources and run `make viewer`. fenolite.view.export.template() inlines it after the page's
// "use strict" prologue and its EMBED and LIVE constants.
/*
 * Preact 10.29.8, bundled below (variable `preact`).
 *
 * The MIT License (MIT)
 *
 * Copyright (c) 2015-present Jason Miller
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */
var preact=(()=>{var B=Object.defineProperty;var he=Object.getOwnPropertyDescriptor;var de=Object.getOwnPropertyNames;var ve=Object.prototype.hasOwnProperty;var me=(t,e)=>{for(var _ in e)B(t,_,{get:e[_],enumerable:!0})},ye=(t,e,_,l)=>{if(e&&typeof e=="object"||typeof e=="function")for(let o of de(e))!ve.call(t,o)&&o!==_&&B(t,o,{get:()=>e[o],enumerable:!(l=he(e,o))||l.enumerable});return t};var ge=t=>ye(B({},"__esModule",{value:!0}),t);var Te={};me(Te,{Component:()=>U,Fragment:()=>T,h:()=>J,render:()=>ae});var I,h,_e,ke,x,Y,ne,re,O,A,D,oe,q,V,z,be,N={},j=[],we=/acit|ex(?:s|g|n|p|$)|rph|grid|ows|mnc|ntw|ine[ch]|zoo|^ord|itera/i,R=Array.isArray;function w(t,e){for(var _ in e)t[_]=e[_];return t}function G(t){t&&t.parentNode&&t.parentNode.removeChild(t)}function J(t,e,_){var l,o,r,i={};for(r in e)r=="key"?l=e[r]:r=="ref"?o=e[r]:i[r]=e[r];if(arguments.length>2&&(i.children=arguments.length>3?I.call(arguments,2):_),typeof t=="function"&&t.defaultProps!=null)for(r in t.defaultProps)i[r]===void 0&&(i[r]=t.defaultProps[r]);return L(t,i,l,o,null)}function L(t,e,_,l,o){var r={type:t,props:e,key:_,ref:l,__k:null,__:null,__b:0,__e:null,__c:null,constructor:void 0,__v:o??++_e,__i:-1,__u:0};return o==null&&h.vnode!=null&&h.vnode(r),r}function T(t){return t.children}function U(t,e){this.props=t,this.context=e}function P(t,e){if(e==null)return t.__?P(t.__,t.__i+1):null;for(var _;e<t.__k.length;e++)if((_=t.__k[e])!=null&&_.__e!=null)return _.__e;return typeof t.type=="function"?P(t):null}function xe(t){if(t.__P&&t.__d){var e=t.__v,_=e.__e,l=[],o=[],r=w({},e);r.__v=e.__v+1,h.vnode&&h.vnode(r),K(t.__P,r,e,t.__n,t.__P.namespaceURI,32&e.__u?[_]:null,l,_??P(e),!!(32&e.__u),o),r.__v=e.__v,r.__.__k[r.__i]=r,ce(l,r,o),e.__e=e.__=null,r.__e!=_&&le(r)}}function le(t){if((t=t.__)!=null&&t.__c!=null)return t.__e=t.__c.base=null,t.__k.some(function(e){if(e!=null&&e.__e!=null)return t.__e=t.__c.base=e.__e}),le(t)}function Z(t){(!t.__d&&(t.__d=!0)&&x.push(t)&&!H.__r++||Y!=h.debounceRendering)&&((Y=h.debounceRendering)||ne)(H)}function H(){try{for(var t,e=1;x.length;)x.length>e&&x.sort(re),t=x.shift(),e=x.length,xe(t)}finally{x.length=H.__r=0}}function ie(t,e,_,l,o,r,i,u,a,s,p){var m,n,c,d,g,y,v=l&&l.__k||j,f=e.length;for(a=Ce(_,e,v,a,f),m=0;m<f;m++)(c=_.__k[m])!=null&&(n=c.__i!=-1&&v[c.__i]||N,c.__i=m,y=K(t,c,n,o,r,i,u,a,s,p),d=c.__e,c.ref&&n.ref!=c.ref&&(n.ref&&Q(n.ref,null,c),p.push(c.ref,c.__c||d,c)),g==null&&d!=null&&(g=d),4&c.__u?(a=se(c,a,t),n.__e&&(n.__e=null)):typeof c.type=="function"&&y!==void 0?a=y:d&&(a=d.nextSibling),c.__u&=-7);return _.__e=g,a}function Ce(t,e,_,l,o){var r,i,u,a,s,p=_.length,m=p,n=0;for(t.__k=new Array(o),r=0;r<o;r++)(i=e[r])!=null&&typeof i!="boolean"&&typeof i!="function"?(typeof i=="string"||typeof i=="number"||typeof i=="bigint"||i.constructor==String?i=t.__k[r]=L(null,i,null,null,null):R(i)?i=t.__k[r]=L(T,{children:i},null,null,null):i.constructor===void 0&&i.__b>0?i=t.__k[r]=L(i.type,i.props,i.key,i.ref?i.ref:null,i.__v):t.__k[r]=i,a=r+n,i.__=t,i.__b=t.__b+1,u=null,(s=i.__i=Pe(i,_,a,m))!=-1&&(m--,(u=_[s])&&(u.__u|=2)),u==null||u.__v==null?(s==-1&&(o>p?n--:o<p&&n++),typeof i.type!="function"&&(i.__u|=4)):s!=a&&(s==a-1?n--:s==a+1?n++:(s>a?n--:n++,i.__u|=4))):t.__k[r]=null;if(m)for(r=0;r<p;r++)(u=_[r])!=null&&(2&u.__u)==0&&(u.__e==l&&(l=P(u)),fe(u,u));return l}function se(t,e,_){var l,o;if(typeof t.type=="function"){for(l=t.__k,o=0;l&&o<l.length;o++)l[o]&&(l[o].__=t,e=se(l[o],e,_));return e}t.__e!=e&&(e&&t.type&&!e.parentNode&&(e=P(t)),e=_.insertBefore(t.__e,e||null));do e=e&&e.nextSibling;while(e!=null&&e.nodeType==8);return e}function Pe(t,e,_,l){var o,r,i,u=t.key,a=t.type,s=e[_],p=s!=null&&(2&s.__u)==0;if(s===null&&u==null||p&&u==s.key&&a==s.type)return _;if(l>(p?1:0)){for(o=_-1,r=_+1;o>=0||r<e.length;)if((s=e[i=o>=0?o--:r++])!=null&&(2&s.__u)==0&&u==s.key&&a==s.type)return i}return-1}function ee(t,e,_){e[0]=="-"?t.setProperty(e,_??""):t[e]=_==null?"":typeof _!="number"||we.test(e)?_:_+"px"}function W(t,e,_,l,o){var r,i;e:if(e=="style")if(typeof _=="string")t.style.cssText=_;else{if(typeof l=="string"&&(t.style.cssText=l=""),l)for(e in l)_&&e in _||ee(t.style,e,"");if(_)for(e in _)l&&_[e]==l[e]||ee(t.style,e,_[e])}else if(e[0]=="o"&&e[1]=="n")r=e!=(e=e.replace(oe,"$1")),i=e.toLowerCase(),e=i in t||e=="onFocusOut"||e=="onFocusIn"?i.slice(2):e.slice(2),t.l||(t.l={}),t.l[e+r]=_,_?l?_[D]=l[D]:(_[D]=q,t.addEventListener(e,r?z:V,r)):t.removeEventListener(e,r?z:V,r);else{if(["http:","","www.w3.org","2000","svg"].join("/")==o)e=e.replace(/xlink(H|:h)/,"h").replace(/sName$/,"s");else if(e!="width"&&e!="height"&&e!="href"&&e!="list"&&e!="form"&&e!="tabIndex"&&e!="download"&&e!="rowSpan"&&e!="colSpan"&&e!="role"&&e!="popover"&&e in t)try{t[e]=_??"";break e}catch{}typeof _=="function"||(_==null||_===!1&&e[4]!="-"?t.removeAttribute(e):t.setAttribute(e,e=="popover"&&_==1?"":_))}}function te(t){return function(e){if(this.l){var _=this.l[e.type+t];if(e[A]==null)e[A]=q++;else if(e[A]<_[D])return;return _(h.event?h.event(e):e)}}}function K(t,e,_,l,o,r,i,u,a,s){var p,m,n,c,d,g,y,v,f,k,M,C,E,X,F,$,b=e.type;if(e.constructor!==void 0)return null;128&_.__u&&(a=!!(32&_.__u),r=[u=e.__e=_.__e]),(p=h.__b)&&p(e);e:if(typeof b=="function"){m=i.length;try{if(f=e.props,k=b.prototype&&b.prototype.render,M=(p=b.contextType)&&l[p.__c],C=p?M?M.props.value:p.__:l,_.__c?v=(n=e.__c=_.__c).__=n.__E:(k?e.__c=n=new b(f,C):(e.__c=n=new U(f,C),n.constructor=b,n.render=Ue),M&&M.sub(n),n.state||(n.state={}),n.__n=l,c=n.__d=!0,n.__h=[],n._sb=[]),k&&n.__s==null&&(n.__s=n.state),k&&b.getDerivedStateFromProps!=null&&(n.__s==n.state&&(n.__s=w({},n.__s)),w(n.__s,b.getDerivedStateFromProps(f,n.__s))),d=n.props,g=n.state,n.__v=e,c)k&&b.getDerivedStateFromProps==null&&n.componentWillMount!=null&&n.componentWillMount(),k&&n.componentDidMount!=null&&n.__h.push(n.componentDidMount);else{if(k&&b.getDerivedStateFromProps==null&&f!==d&&n.componentWillReceiveProps!=null&&n.componentWillReceiveProps(f,C),e.__v==_.__v||!n.__e&&n.shouldComponentUpdate!=null&&n.shouldComponentUpdate(f,n.__s,C)===!1){e.__v!=_.__v&&(n.props=f,n.state=n.__s,n.__d=!1),e.__e=_.__e,e.__k=_.__k,e.__k.some(function(S){S&&(S.__=e)}),j.push.apply(n.__h,n._sb),n._sb=[],n.__h.length&&i.push(n),u=P(_);break e}n.componentWillUpdate!=null&&n.componentWillUpdate(f,n.__s,C),k&&n.componentDidUpdate!=null&&n.__h.push(function(){n.componentDidUpdate(d,g,y)})}if(n.context=C,n.props=f,n.__P=t,n.__e=!1,E=h.__r,X=0,k)n.state=n.__s,n.__d=!1,E&&E(e),p=n.render(n.props,n.state,n.context),j.push.apply(n.__h,n._sb),n._sb=[];else do n.__d=!1,E&&E(e),p=n.render(n.props,n.state,n.context),n.state=n.__s;while(n.__d&&++X<25);n.state=n.__s,n.getChildContext!=null&&(l=w(w({},l),n.getChildContext())),k&&!c&&n.getSnapshotBeforeUpdate!=null&&(y=n.getSnapshotBeforeUpdate(d,g)),F=p!=null&&p.type===T&&p.key==null?pe(p.props.children):p,u=ie(t,R(F)?F:[F],e,_,l,o,r,i,u,a,s),n.base=e.__e,e.__u&=-161,n.__h.length&&i.push(n),v&&(n.__E=n.__=null)}catch(S){if(i.length=m,e.__v=null,a||r!=null){if(S.then){for(e.__u|=a?160:128;u&&u.nodeType==8&&u.nextSibling;)u=u.nextSibling;r!=null&&(r[r.indexOf(u)]=null),e.__e=u}else if(r!=null)for($=r.length;$--;)G(r[$])}else e.__e=_.__e;e.__k==null&&(e.__k=_.__k||[]),S.then||ue(e),h.__e(S,e,_)}}else r==null&&e.__v==_.__v?(e.__k=_.__k,e.__e=_.__e):u=e.__e=Se(_.__e,e,_,l,o,r,i,a,s);return(p=h.diffed)&&p(e),128&e.__u?void 0:u}function ue(t){t&&(t.__c&&(t.__c.__e=!0),t.__k&&t.__k.some(ue))}function ce(t,e,_){for(var l=0;l<_.length;l++)Q(_[l],_[++l],_[++l]);h.__c&&h.__c(e,t),t.some(function(o){try{t=o.__h,o.__h=[],t.some(function(r){r.call(o)})}catch(r){h.__e(r,o.__v)}})}function pe(t){return typeof t!="object"||t==null||t.__b>0?t:R(t)?t.map(pe):t.constructor!==void 0?null:w({},t)}function Se(t,e,_,l,o,r,i,u,a){var s,p,m,n,c,d,g,y=_.props||N,v=e.props,f=e.type;if(f=="svg"?o=["http:","","www.w3.org","2000","svg"].join("/"):f=="math"?o=["http:","","www.w3.org","1998","Math","MathML"].join("/"):o||(o=["http:","","www.w3.org","1999","xhtml"].join("/")),r!=null){for(s=0;s<r.length;s++)if((c=r[s])&&"setAttribute"in c==!!f&&(f?c.localName==f:c.nodeType==3)){t=c,r[s]=null;break}}if(t==null){if(f==null)return document.createTextNode(v);t=document.createElementNS(o,f,v.is&&v),u&&(h.__m&&h.__m(e,r),u=!1),r=null}if(f==null)y===v||u&&t.data==v||(t.data=v);else{if(r=f=="textarea"&&v.defaultValue!=null?null:r&&I.call(t.childNodes),!u&&r!=null)for(y={},s=0;s<t.attributes.length;s++)y[(c=t.attributes[s]).name]=c.value;for(s in y)c=y[s],s=="dangerouslySetInnerHTML"?m=c:s=="children"||s in v||s=="value"&&"defaultValue"in v||s=="checked"&&"defaultChecked"in v||W(t,s,null,c,o);for(s in v)c=v[s],s=="children"?n=c:s=="dangerouslySetInnerHTML"?p=c:s=="value"?d=c:s=="checked"?g=c:u&&typeof c!="function"||y[s]===c||W(t,s,c,y[s],o);if(p)u||m&&(p.__html==m.__html||p.__html==t.innerHTML)||(t.innerHTML=p.__html),e.__k=[];else if(m&&(t.innerHTML=""),ie(e.type=="template"?t.content:t,R(n)?n:[n],e,_,l,f=="foreignObject"?["http:","","www.w3.org","1999","xhtml"].join("/"):o,r,i,r?r[0]:_.__k&&P(_,0),u,a),r!=null)for(s=r.length;s--;)G(r[s]);u&&f!="textarea"||(s="value",f=="progress"&&d==null?t.removeAttribute("value"):d!=null&&(d!==t[s]||f=="progress"&&!d||f=="option"&&d!=y[s])&&W(t,s,d,y[s],o),s="checked",g!=null&&g!=t[s]&&W(t,s,g,y[s],o))}return t}function Q(t,e,_){try{if(typeof t=="function"){var l=typeof t.__u=="function";l&&t.__u(),l&&e==null||(t.__u=t(e))}else t.current=e}catch(o){h.__e(o,_)}}function fe(t,e,_){var l,o;if(h.unmount&&h.unmount(t),(l=t.ref)&&(l.current&&l.current!=t.__e||Q(l,null,e)),(l=t.__c)!=null){if(l.componentWillUnmount)try{l.componentWillUnmount()}catch(r){h.__e(r,e)}l.base=l.__P=l.__n=null}if(l=t.__k)for(o=0;o<l.length;o++)l[o]&&fe(l[o],e,_||typeof t.type!="function");_||G(t.__e),t.__c=t.__=t.__e=void 0}function Ue(t,e,_){return this.constructor(t,_)}function ae(t,e,_){var l,o,r,i;e==document&&(e=document.documentElement),h.__&&h.__(t,e),o=(l=typeof _=="function")?null:_&&_.__k||e.__k,r=[],i=[],K(e,t=(!l&&_||e).__k=J(T,null,[t]),o||N,N,e.namespaceURI,!l&&_?[_]:o?null:e.firstChild?I.call(e.childNodes):null,r,!l&&_?_:o?o.__e:e.firstChild,l,i),ce(r,t,i),t.props.children=null}I=j.slice,h={__e:function(t,e,_,l){for(var o,r,i;e=e.__;)if((o=e.__c)&&!o.__)try{if((r=o.constructor)&&r.getDerivedStateFromError!=null&&(o.setState(r.getDerivedStateFromError(t)),i=o.__d),o.componentDidCatch!=null&&(o.componentDidCatch(t,l||{}),i=o.__d),i)return o.__E=o}catch(u){t=u}throw t}},_e=0,ke=function(t){return t!=null&&t.constructor===void 0},U.prototype.setState=function(t,e){var _;_=this.__s!=null&&this.__s!=this.state?this.__s:this.__s=w({},this.state),typeof t=="function"&&(t=t(w({},_),this.props)),t&&w(_,t),t!=null&&this.__v&&(e&&this._sb.push(e),Z(this))},U.prototype.forceUpdate=function(t){this.__v&&(this.__e=!0,t&&this.__h.push(t),Z(this))},U.prototype.render=T,x=[],ne=typeof Promise=="function"?Promise.prototype.then.bind(Promise.resolve()):setTimeout,re=function(t,e){return t.__v.__b-e.__v.__b},H.__r=0,O=Math.random().toString(8),A="__d"+O,D="__a"+O,oe=/(PointerCapture)$|Capture$/i,q=0,V=te(!1),z=te(!0),be=0;return ge(Te);})();
// ---- core/env.ts
const PREVIEW_MODE = new URLSearchParams(location.hash.slice(1)).get("preview") === "1";
if (PREVIEW_MODE)
    document.body.classList.add("preview");
// ---- core/dom.ts
const $ = (id) => document.getElementById(id); // any: the page reads value, checked, showModal… of what it finds
// A message of HTML in the inspector (c0301: the dock's Properties tab); a selection uses showModel of panels/inspector.
function showInfo(html) { if (!html)
    renderInspector(null);
else
    showModel({ kind: "note", title: "", sections: [], html }); }
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" })[c]); }
function linkify(v) { const t = String(v); return /^https?:\/\/\S+$/i.test(t) ? `<a href="${esc(t)}" target="_blank" rel="noopener noreferrer">${esc(t)}</a>` : esc(t); }
function natural(a, b) { return a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" }); }
function download(text, name, type) { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000); }
// ---- ui/icons.tsx
// The interface icons (c0300, design decision 3): drawn for Fenolite on a 16-pixel grid as stroked paths in
// currentColor, 1.5 px wide, rendered inline by one Preact component; no icon font, no third-party set.
// ---- icons (c0300)
const ICONS = {
    sidebar: "M3.5 2.75h9a1.75 1.75 0 0 1 1.75 1.75v7a1.75 1.75 0 0 1-1.75 1.75h-9a1.75 1.75 0 0 1-1.75-1.75v-7A1.75 1.75 0 0 1 3.5 2.75zM6.25 2.75v10.5",
    dock: "M3.5 2.75h9a1.75 1.75 0 0 1 1.75 1.75v7a1.75 1.75 0 0 1-1.75 1.75h-9a1.75 1.75 0 0 1-1.75-1.75v-7A1.75 1.75 0 0 1 3.5 2.75zM9.75 2.75v10.5",
    info: "M14.25 8A6.25 6.25 0 1 1 1.75 8a6.25 6.25 0 0 1 12.5 0zM8 7.5v3.75M8 4.9v.1",
    plane: "M8 4.25l5.75 3.25L8 10.75 2.25 7.5z",
    cube: "M8 1.75l5.5 3v6.5L8 14.25l-5.5-3v-6.5zM2.5 4.75 8 7.75l5.5-3M8 7.75v6.5",
    fit: "M2.25 5.75v-3.5h3.5M10.25 2.25h3.5v3.5M13.75 10.25v3.5h-3.5M5.75 13.75h-3.5v-3.5",
    flip: "M5 2.5v9.5M2.75 9.75 5 12l2.25-2.25M11 13.5V4M8.75 6.25 11 4l2.25 2.25",
    ruler: "M1.9 11.1 11.1 1.9l3 3-9.2 9.2zM4.5 8.5l1.5 1.5M6.75 6.25l1.5 1.5M9 4l1.5 1.5",
    gap: "M2.75 2.75v10.5M13.25 2.75v10.5M5.25 8h5.5M6.75 6.5 5.25 8l1.5 1.5M9.25 6.5 10.75 8l-1.5 1.5",
    pin: "M8 14.25s4.75-4.2 4.75-7.75a4.75 4.75 0 0 0-9.5 0c0 3.55 4.75 7.75 4.75 7.75zM8 8.25a1.75 1.75 0 1 0 0-3.5 1.75 1.75 0 0 0 0 3.5z",
    units: "M1.75 5.25h12.5v5.5H1.75zM4.75 5.25v2.5M8 5.25v3.25M11.25 5.25v2.5",
    link: "M6.75 9.25a3 3 0 0 0 4.25 0l2-2a3 3 0 0 0-4.25-4.25l-.75.75M9.25 6.75a3 3 0 0 0-4.25 0l-2 2a3 3 0 0 0 4.25 4.25l.75-.75",
    download: "M8 2.25v8M4.75 7 8 10.25 11.25 7M2.75 11.75v1.5h10.5v-1.5",
    image: "M2.75 2.75h10.5v10.5H2.75zM2.75 10.75l3-3 2.5 2.5 1.75-1.75 3.25 3.25M10.25 5.5v.1",
    printer: "M4.25 6V2.25h7.5V6M4.25 11.5h-1.5V6h10.5v5.5h-1.5M4.25 9.25h7.5v4.5h-7.5z",
    search: "M7 12.25a5.25 5.25 0 1 0 0-10.5 5.25 5.25 0 0 0 0 10.5zM14.25 14.25l-3.5-3.5",
    keyboard: "M1.75 4.25h12.5v7.5H1.75zM4.25 6.75v.1M6.75 6.75v.1M9.25 6.75v.1M11.75 6.75v.1M4.75 9.25h6.5",
    sun: "M8 10.75a2.75 2.75 0 1 0 0-5.5 2.75 2.75 0 0 0 0 5.5zM8 1.25v1.5M8 13.25v1.5M1.25 8h1.5M13.25 8h1.5M3.2 3.2l1.05 1.05M11.75 11.75l1.05 1.05M3.2 12.8l1.05-1.05M11.75 4.25l1.05-1.05",
    moon: "M13.5 9.75A5.75 5.75 0 0 1 6.25 2.5a5.75 5.75 0 1 0 7.25 7.25z",
    monitor: "M1.75 2.75h12.5v8.5H1.75zM5.5 14.25h5M8 11.25v3",
    x: "M4 4l8 8M12 4l-8 8",
    chevDown: "M4.5 6.25 8 9.75l3.5-3.5",
    chevRight: "M6.25 4.5 9.75 8l-3.5 3.5",
    check: "M3 8.5l3.25 3.25L13 5",
    play: "M5 2.9v10.2L13 8z",
    review: "M5.75 2.75h-2v11h8.5v-11h-2M5.75 1.75h4.5v2h-4.5zM5.5 9l1.75 1.75 3.25-3.5",
    sliders: "M2.25 4.5h7M12.5 4.5h1.25M9.75 2.75v3.5M2.25 11.5h1.25M6.25 11.5h7.5M3.75 9.75v3.5",
    copy: "M5.75 5.75h7.5v7.5h-7.5zM3.25 10.25h-.5v-7.5h7.5v.5",
    zoom: "M7 12.25a5.25 5.25 0 1 0 0-10.5 5.25 5.25 0 0 0 0 10.5zM14.25 14.25l-3.5-3.5M7 4.75v4.5M4.75 7h4.5",
    net: "M3.5 5.25a1.75 1.75 0 1 0 0-3.5 1.75 1.75 0 0 0 0 3.5zM12.5 14.25a1.75 1.75 0 1 0 0-3.5 1.75 1.75 0 0 0 0 3.5zM3.5 5.25V8.5h9v2.25",
    chip: "M4.25 4.25h7.5v7.5h-7.5zM6.25 1.75v2.5M9.75 1.75v2.5M6.25 11.75v2.5M9.75 11.75v2.5M1.75 6.25h2.5M1.75 9.75h2.5M11.75 6.25h2.5M11.75 9.75h2.5",
    similar: "M2.25 2.25h7v7h-7zM6.75 6.75h7v7h-7z",
    schematic: "M1.75 8h2.5l1-2.5 2 5 2-5 2 5 1-2.5h2",
    board: "M2.75 2.75h10.5v10.5H2.75zM5.5 5.5h2.25l2.75 2.75v2.25M5.5 10.5v.1",
    alert: "M8 2.25 14.25 13.25H1.75zM8 6.5v3.25M8 11.4v.1",
    eye: "M1.25 8S3.75 3.25 8 3.25 14.75 8 14.75 8 12.25 12.75 8 12.75 1.25 8 1.25 8zM8 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
    eyeOff: "M2.25 2.25l11.5 11.5M6.6 6.6a2 2 0 0 0 2.8 2.8M4.3 4.4C2.3 5.6 1.25 8 1.25 8S3.75 12.75 8 12.75c1.3 0 2.4-.4 3.4-1M7 3.3c.3 0 .7-.05 1-.05 4.25 0 6.75 4.75 6.75 4.75s-.5 1-1.5 2.1",
    waive: "M8 1.75l5.25 2v4c0 3.25-2.25 5.5-5.25 6.5-3-1-5.25-3.25-5.25-6.5v-4zM5.5 8l1.75 1.75 3.25-3.5",
    move: "M8 1.75v12.5M1.75 8h12.5M6 3.75l2-2 2 2M6 12.25l2 2 2-2M3.75 6l-2 2 2 2M12.25 6l2 2-2 2",
    refresh: "M13.25 2.75v3.5h-3.5M13 6.25A5.25 5.25 0 1 0 13.25 9",
    target: "M8 12.75a4.75 4.75 0 1 0 0-9.5 4.75 4.75 0 0 0 0 9.5zM8 .75v3M8 12.25v3M.75 8h3M12.25 8h3",
    changes: "M3 4.5h4.5M5.25 2.25v4.5M8.5 11.5H13M2.75 13.25 13.25 2.75",
    layers: "M8 2 13.75 5 8 8 2.25 5zM2.25 8 8 11l5.75-3M2.25 11 8 14l5.75-3",
    layer: "M8 4.5l5.75 3L8 10.5 2.25 7.5z",
    arrowUp: "M8 13V3M4.25 6.75 8 3l3.75 3.75",
    arrowDown: "M8 3v10M4.25 9.25 8 13l3.75-3.75",
    clear: "M14.25 8A6.25 6.25 0 1 1 1.75 8a6.25 6.25 0 0 1 12.5 0zM5.75 5.75l4.5 4.5M10.25 5.75l-4.5 4.5",
    filter: "M2.25 3h11.5L9.25 8.5v4.75l-2.5-1.25V8.5z",
    doc: "M4 1.75h5.25l3 3v9.5H4zM9 1.75V5h3.25",
    folder: "M1.75 3.25h4.5l1.5 1.5h6.5v8H1.75z",
    more: "M3.5 8v.1M8 8v.1M12.5 8v.1",
    list: "M5.75 4h8M5.75 8h8M5.75 12h8M2.25 4v.1M2.25 8v.1M2.25 12v.1",
    note: "M2.75 2.75h10.5v7.5l-3 3h-7.5zM10.25 13.25v-3h3M5.25 6h5.5M5.25 8.5h3.5",
    hash: "M3 6h10.5M2.5 10H13M6.5 2.25l-1.5 11.5M11 2.25 9.5 13.75",
    at: "M10.75 8a2.75 2.75 0 1 1-5.5 0 2.75 2.75 0 0 1 5.5 0zM10.75 8v1.25a1.75 1.75 0 0 0 3.5 0V8a6.25 6.25 0 1 0-2.5 5",
    stop: "M4.25 4.25h7.5v7.5h-7.5z",
};
// ---- end icons
function Icon({ name, size }) {
    const d = ICONS[name] || ICONS.more, s = size || 16;
    return preact.h("svg", { class: "ic", width: s, height: s, viewBox: "0 0 16 16", fill: "none", stroke: "currentColor", "stroke-width": "1.5", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true", focusable: "false" },
        preact.h("path", { d: d }));
}
// ---- ui/tooltip.tsx
// The tooltip (c0300, design decision 3): one positioned element that shows the title of the control under the
// pointer or with the keyboard focus, after 400 ms, and its shortcut in <kbd>. A control declares them as
// data-tip and data-keys (keys separated by commas); native title tooltips are not used for these controls.
let tipTimer = 0, tipFor = null;
const tipHost = document.createElement("div");
tipHost.id = "tipHost";
document.body.appendChild(tipHost);
function Tooltip({ text, keys, x, y, below }) {
    return preact.h("div", { id: "tip", role: "tooltip", class: below ? "below" : "above", style: `left:${x}px;top:${y}px` },
        preact.h("span", null, text),
        keys.map(k => preact.h("kbd", null, k)));
}
function hideTip() { clearTimeout(tipTimer); tipFor = null; preact.render(null, tipHost); }
function showTip(el) {
    if (!el.isConnected || el.getAttribute("aria-expanded") === "true")
        return;
    const r = el.getBoundingClientRect(), keys = (el.dataset.keys || "").split(",").map(k => k.trim()).filter(Boolean);
    const below = r.bottom + 40 < innerHeight;
    const x = Math.min(Math.max(8, r.left + r.width / 2), innerWidth - 8), y = below ? r.bottom + 6 : r.top - 6;
    preact.render(preact.h(Tooltip, { text: el.dataset.tip, keys: keys, x: x, y: y, below: below }), tipHost);
    const tip = tipHost.firstElementChild; // kept inside the window
    if (tip) {
        const w = tip.offsetWidth;
        tip.style.left = `${Math.min(Math.max(8 + w / 2, x), innerWidth - 8 - w / 2)}px`;
    }
}
function tipTarget(e) { const t = e.target; return t && t.closest ? t.closest("[data-tip]") : null; }
function arm(el) { if (el === tipFor)
    return; hideTip(); if (!el || !el.dataset.tip)
    return; tipFor = el; tipTimer = setTimeout(() => showTip(el), 400); }
document.addEventListener("pointerover", e => arm(tipTarget(e)));
document.addEventListener("pointerout", e => { const to = e.relatedTarget; if (!to || !tipFor || !tipFor.contains(to))
    hideTip(); });
document.addEventListener("focusin", e => { const el = tipTarget(e); if (el && el.matches(":focus-visible"))
    arm(el);
else
    hideTip(); });
document.addEventListener("focusout", hideTip);
for (const type of ["pointerdown", "keydown", "wheel", "scroll"])
    document.addEventListener(type, hideTip, true);
// ---- ui/toast.tsx
// Short confirmations (c0300): "Link copied", "Copied", a copy that failed. One message at a time at the foot of
// the drawing, read by screen readers (role="status"), gone after three seconds. And the clipboard: the
// asynchronous API, else a hidden textarea and execCommand("copy") for a page opened from file:// (c0301).
const toastHost = document.createElement("div");
toastHost.id = "toastHost";
document.body.appendChild(toastHost);
let toastTimer = 0;
function toast(text, kind = "ok") {
    clearTimeout(toastTimer);
    preact.render(preact.h("div", { id: "toast", class: kind, role: "status", "aria-live": "polite" }, text), toastHost);
    toastTimer = setTimeout(() => preact.render(null, toastHost), 3000);
}
async function copyText(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    }
    catch (e) { /* refused: the fallback below */ }
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.cssText = "position:fixed;left:-9999px;top:0;opacity:0";
    document.body.appendChild(area);
    const focus = document.activeElement;
    area.select();
    let ok = false;
    try {
        ok = document.execCommand("copy");
    }
    catch (e) {
        ok = false;
    }
    area.remove();
    focus?.focus?.();
    return ok;
}
async function copyAndSay(text, what = "Copied") {
    const ok = await copyText(text);
    toast(ok ? what : "The browser refused the clipboard: select the text and copy it", ok ? "ok" : "err");
    return ok;
}
// ---- ui/menu.tsx
// A menu button (c0300, design decision 3): a toolbar button with aria-haspopup that opens a list of items
// (role="menu") or a small panel under it. The list is placed with fixed coordinates, so no scrolling parent clips
// it; arrows move between items, Enter runs one, Esc closes and gives the focus back to the button, and a click
// elsewhere closes it.
let OPEN_MENU = null;
function closeMenus() { if (OPEN_MENU)
    OPEN_MENU.close(false); }
class Menu extends preact.Component {
    constructor(props) { super(props); this.state = { open: false, x: 0, y: 0 }; }
    outside = (e) => { const t = e.target; if (this.list?.contains(t) || this.button?.contains(t))
        return; this.close(false); };
    open() {
        if (OPEN_MENU && OPEN_MENU !== this)
            OPEN_MENU.close(false);
        const r = this.button.getBoundingClientRect(), w = 232;
        const x = this.props.align === "right" || r.left + w > innerWidth - 8 ? Math.max(8, r.right - w) : r.left;
        OPEN_MENU = this;
        this.setState({ open: true, x, y: r.bottom + 6 }, () => {
            document.addEventListener("pointerdown", this.outside, true);
            this.list?.querySelector("[role^=menuitem]:not([disabled]), input, select, button")?.focus();
        });
    }
    close(focus = true) {
        document.removeEventListener("pointerdown", this.outside, true);
        if (OPEN_MENU === this)
            OPEN_MENU = null;
        if (this.state.open)
            this.setState({ open: false });
        if (focus)
            this.button?.focus();
    }
    componentWillUnmount() { document.removeEventListener("pointerdown", this.outside, true); if (OPEN_MENU === this)
        OPEN_MENU = null; }
    onKey = (e) => {
        if (e.key === "Escape") {
            e.preventDefault();
            e.stopPropagation();
            this.close();
            return;
        }
        if (e.key !== "ArrowDown" && e.key !== "ArrowUp")
            return;
        const items = [...this.list.querySelectorAll("[role^=menuitem]:not([disabled])")];
        if (!items.length)
            return;
        e.preventDefault();
        const i = items.indexOf(document.activeElement);
        items[(i + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length].focus();
    };
    choose(it) { if (it.disabled)
        return; this.close(); it.run && it.run(); }
    render(p, s) {
        return preact.h("span", { class: "menuWrap" + (p.cls ? " " + p.cls : "") },
            preact.h("button", { id: p.id, type: "button", class: "tb" + (p.caret ? " caret" : "") + (p.showLabel === false || !p.text ? " icon" : ""), "aria-haspopup": "menu", "aria-expanded": Boolean(s.open), "aria-label": p.label, "aria-pressed": p.pressed, "data-tip": p.tip || p.label, "data-keys": p.keys || undefined, ref: el => { this.button = el; }, onClick: () => s.open ? this.close() : this.open(), onKeyDown: e => { if (e.key === "ArrowDown" && !s.open) {
                    e.preventDefault();
                    this.open();
                } } },
                p.icon ? preact.h(Icon, { name: p.icon }) : null,
                p.text ? preact.h("span", { class: "lbl" }, p.text) : null,
                p.caret ? preact.h(Icon, { name: "chevDown", size: 12 }) : null),
            s.open ? preact.h("div", { class: "menu" + (p.panel ? " menuPanel" : ""), role: p.panel ? "dialog" : "menu", "aria-label": p.label, style: `left:${s.x}px;top:${s.y}px`, ref: el => { this.list = el; }, onKeyDown: this.onKey }, p.panel ? p.panel() : (p.items || []).map((it, k) => it.sep ? preact.h("div", { key: k, class: "menuSep", role: "separator" })
                : it.heading ? preact.h("div", { key: k, class: "menuHead" }, it.heading)
                    : preact.h("button", { key: k, id: it.id, type: "button", role: it.radio ? "menuitemradio" : it.checked !== undefined ? "menuitemcheckbox" : "menuitem", "aria-checked": it.checked, disabled: it.disabled, class: "menuItem", onClick: () => this.choose(it) },
                        preact.h("span", { class: "menuIc" }, it.checked ? preact.h(Icon, { name: "check" }) : it.icon ? preact.h(Icon, { name: it.icon }) : null),
                        preact.h("span", { class: "menuText" },
                            it.title,
                            it.hint ? preact.h("small", null, it.hint) : null),
                        it.keys ? preact.h("kbd", null, it.keys) : null))) : null);
    }
}
// ---- ui/section.tsx
// The side bar's sections (c0300, design decision 5): each panel is a <details class="sect"> whose summary holds
// a chevron, the title and a count; the open state of each is kept in localStorage (fenolite.view.sections).
// A section that has nothing to show for the open document is hidden; showSection() sets its title, count and
// visibility, and keeps the id of the title element the tests and the panels read (diffTitle, msgTitle, …).
const SECTION_KEY = "fenolite.view.sections";
const sectState = (() => { try {
    return JSON.parse(localStorage.getItem(SECTION_KEY) || "{}") || {};
}
catch (e) {
    return {};
} })();
const sectHeads = new Map();
function SectionHead({ title, count, titleId, tone }) {
    return preact.h(preact.Fragment, null,
        preact.h("span", { class: "chev" },
            preact.h(Icon, { name: "chevRight", size: 12 })),
        preact.h("span", { class: "sectTitle", id: titleId }, title),
        count === undefined || count === null || count === "" ? null : preact.h("span", { class: "count" + (tone ? " " + tone : "") }, String(count)));
}
function renderHead(el) {
    const h = sectHeads.get(el.dataset.sect);
    preact.render(preact.h(SectionHead, { ...h }), el.querySelector(":scope > summary"));
}
function initSections() {
    for (const el of document.querySelectorAll("details.sect")) {
        const id = el.dataset.sect;
        sectHeads.set(id, { title: el.dataset.title || id, titleId: el.dataset.titleId || undefined });
        if (id in sectState)
            el.open = !!sectState[id];
        el.addEventListener("toggle", () => {
            sectState[id] = el.open;
            try {
                localStorage.setItem(SECTION_KEY, JSON.stringify(sectState));
            }
            catch (e) { /* kept for this page only */ }
        });
        renderHead(el);
    }
}
function sectionEl(id) { return document.querySelector(`details.sect[data-sect="${id}"]`); }
function showSection(id, visible, count, title, tone) {
    const el = sectionEl(id);
    if (!el)
        return;
    el.hidden = !visible;
    const h = sectHeads.get(id) || { title: id };
    sectHeads.set(id, { ...h, title: title ?? h.title, count, tone });
    renderHead(el);
}
initSections();
// ---- ui/states.tsx
// Loading, empty and error states (c0300, design decision 7): the document card over the drawing (reading,
// a failed read with Retry, a missing file, a kind without a viewer, a project without a viewable document), the
// indeterminate progress bar under the toolbar, and the line a list shows when it has nothing to list.
const VIEWABLE_KINDS = ["Boards (.kicad_pcb, .PcbDoc)", "Schematics (.kicad_sch, .SchDoc)", "Symbol and footprint libraries",
    "Draftsman drawings (.PCBDwf)", "Bills of materials and output jobs"];
function fmtSize(n) { return n == null ? "size unknown" : n >= 1024 ? `${(n / 1024).toFixed(1)} kB` : `${n} bytes`; }
function DocCard({ doc, state, error, onRetry, project }) {
    const icon = state === "error" ? "alert" : state === "reading" ? "doc" : "info";
    return preact.h("div", { class: "cardBox " + state, role: state === "error" ? "alert" : "status" },
        preact.h("div", { class: "cardIc" },
            preact.h(Icon, { name: icon, size: 20 })),
        preact.h("div", { class: "cardMain" },
            preact.h("h2", null, doc ? doc.name : "Nothing to show"),
            doc ? preact.h("p", { class: "cardMeta" }, `${doc.kind} · ${doc.path} · ${fmtSize(doc.size)}`) : null,
            state === "reading" ? preact.h("p", null,
                "Reading\u2026 ",
                preact.h("span", { class: "spin", "aria-hidden": "true" })) : null,
            state === "error" ? preact.h(preact.Fragment, null,
                preact.h("p", { class: "cardErr" }, `Could not read it: ${error}`),
                preact.h("div", { class: "cardActions" },
                    preact.h("button", { id: "docRetry", type: "button", class: "tb accentBtn", onClick: onRetry },
                        preact.h(Icon, { name: "refresh" }),
                        preact.h("span", { class: "lbl" }, "Retry")))) : null,
            state === "missing" ? preact.h("p", null, "The file is not in the project folder.") : null,
            state === "noviewer" ? preact.h("p", null, project ? "This project holds no document Fenolite can draw yet." : "Fenolite has no viewer for this kind of document yet.") : null,
            state === "noviewer" || state === "missing" ? preact.h(preact.Fragment, null,
                preact.h("p", { class: "cardSub" }, "These kinds open in the viewer:"),
                preact.h("ul", { class: "cardKinds" }, VIEWABLE_KINDS.map(k => preact.h("li", null, k)))) : null,
            state === "empty" ? preact.h("p", null, "The scene is empty.") : null));
}
function Empty({ text, icon }) {
    return preact.h("div", { class: "empty", role: "note" },
        preact.h(Icon, { name: icon || "info" }),
        preact.h("span", null, text));
}
function emptyNote(box, text, icon) { preact.render(preact.h(Empty, { text: text, icon: icon }), box); }
function setLoading(on) { document.getElementById("progress")?.classList.toggle("on", on); }
// ---- core/state.ts
// ================================================================== state
const MM = 0.001; // scene units are micrometres
// The state the modules share (change c0304, design decision 5): a `let` that another module assigns has its
// setter here; the objects are mutated in place.
let PROJECT = null, DOC = null, S = null;
function setProject(v) { PROJECT = v; }
function setDoc(v) { DOC = v; }
function setS(v) { S = v; }
const SCENES = new Map(), RAW = new Map();
const SCENE_READS = new Map(), POLLS = new Map(); // latest request per document, including cache invalidations
const cv = document.getElementById("cv");
let ctx = cv.getContext("2d"), P2D = Path2D; // c0189: both swapped while an SVG is recorded
function setCtx(v) { ctx = v; }
function setP2D(v) { P2D = v; }
const view = { cx: 0, cy: 0, s: 5, mirror: false };
const st = { edge: false, epick: [], eres: null, marking: false, checks: true, selFinding: -1, query: null, hl: (() => { try {
        return localStorage.getItem("fenolite.view.highlight") || "dim";
    }
    catch (e) {
        return "dim";
    } })(), diff: true, single: false, measure: false, mpts: [], selNet: -1, selComp: -1, selOv: -1, opac: 0.6, version: null, mode3d: false, cur: null,
    ovOff: new Set(), ovOpen: new Set() };
const vis = new Map();
// ---- core/theme.ts
// The interface theme (c0300, design decision 1): "system" follows prefers-color-scheme, "dark" and "light" are
// the user's choice, kept in localStorage under fenolite.view.theme and written to html[data-theme]. Only the
// chrome changes; a document keeps the colours of its scene.
const THEMES = ["system", "dark", "light"];
let THEME = (() => { try {
    const t = localStorage.getItem("fenolite.view.theme");
    return THEMES.includes(t) ? t : "system";
}
catch (e) {
    return "system";
} })();
function applyTheme() {
    if (THEME === "system")
        document.documentElement.removeAttribute("data-theme");
    else
        document.documentElement.setAttribute("data-theme", THEME);
}
function themeIsLight() {
    return THEME === "light" || (THEME === "system" && matchMedia("(prefers-color-scheme: light)").matches);
}
function setTheme(t) {
    THEME = THEMES.includes(t) ? t : "system";
    try {
        localStorage.setItem("fenolite.view.theme", THEME);
    }
    catch (e) { /* the choice is kept for this page only */ }
    applyTheme();
    themeChanged();
}
function themeChanged() { refreshToolbar(); } // what reads the theme outside CSS: the toolbar's theme icon
applyTheme();
matchMedia("(prefers-color-scheme: light)").addEventListener?.("change", () => { if (THEME === "system")
    themeChanged(); });
// ---- core/font.ts
// ================================================================== stroke font
// Fenolite's own single-stroke font: cap height 6 units, glyph 4 units wide, advance 6 units, x-height 4,
// descender -2. A stroke is "x,y x,y ..." or an elliptic arc "@cx,cy,rx,ry,a1,a2" (degrees; a2 < a1 runs clockwise).
const FONT = {
    " ": [], "A": ["0,0 2,6 4,0", "0.67,2 3.33,2"], "B": ["0,0 0,6 2.6,6", "@2.6,4.5,1.4,1.5,90,-90", "0,3 2.8,3", "@2.8,1.5,1.2,1.5,90,-90", "2.8,0 0,0"],
    "C": ["@2,3,2,3,40,320"], "D": ["0,0 0,6 2,6", "@2,3,2,3,90,-90", "2,0 0,0"], "E": ["4,6 0,6 0,0 4,0", "0,3 2.8,3"], "F": ["4,6 0,6 0,0", "0,3 2.8,3"],
    "G": ["@2,3,2,3,45,355", "4,2.6 2.4,2.6"], "H": ["0,0 0,6", "4,0 4,6", "0,3 4,3"], "I": ["2,0 2,6", "1,6 3,6", "1,0 3,0"],
    "J": ["4,6 4,1.5", "@2,1.5,2,1.5,0,-180"], "K": ["0,0 0,6", "4,6 0,2", "1.4,3.3 4,0"], "L": ["0,6 0,0 4,0"], "M": ["0,0 0,6 2,2.5 4,6 4,0"],
    "N": ["0,0 0,6 4,0 4,6"], "O": ["@2,3,2,3,0,360"], "P": ["0,0 0,6 2.6,6", "@2.6,4.5,1.4,1.5,90,-90", "2.6,3 0,3"],
    "Q": ["@2,3,2,3,0,360", "2.5,1.5 4,0"], "R": ["0,0 0,6 2.6,6", "@2.6,4.5,1.4,1.5,90,-90", "2.6,3 0,3", "2.2,3 4,0"],
    "S": ["@2,4.5,2,1.5,20,270", "@2,1.5,2,1.5,90,-160"], "T": ["0,6 4,6", "2,6 2,0"], "U": ["0,6 0,1.5", "@2,1.5,2,1.5,180,360", "4,1.5 4,6"],
    "V": ["0,6 2,0 4,6"], "W": ["0,6 1,0 2,4 3,0 4,6"], "X": ["0,6 4,0", "0,0 4,6"], "Y": ["0,6 2,3 4,6", "2,3 2,0"], "Z": ["0,6 4,6 0,0 4,0"],
    "0": ["@2,3,2,3,0,360"], "1": ["0.8,4.8 2,6 2,0", "1,0 3,0"], "2": ["@2,4.3,2,1.7,165,-25", "3.81,3.58 0,0 4,0"],
    "3": ["@2,4.5,1.9,1.5,150,-90", "@2,1.5,2,1.5,90,-150"], "4": ["3,0 3,6 0,1.8 4,1.8"], "5": ["4,6 0.4,6 0.47,3.12", "@2,1.9,2,1.9,140,-150"],
    "6": ["3.6,5.5 3.2,5.85 2,6 1,5.7 0.3,4.6 0,3 0,1.8", "@2,1.8,2,1.8,180,540"], "7": ["0,6 4,6 1.4,0"],
    "8": ["@2,4.5,1.7,1.5,0,360", "@2,1.5,2,1.5,0,360"], "9": ["@2,4.2,2,1.8,0,360", "4,4.2 4,2 3.3,0.6 2,0 0.6,0.4"],
    "a": ["@2,2,2,2,0,360", "4,4 4,0"], "b": ["0,6 0,0", "@2,2,2,2,180,540"], "c": ["@2,2,2,2,40,320"], "d": ["4,6 4,0", "@2,2,2,2,0,360"],
    "e": ["0.05,2 4,2 3.9,2.7 3.5,3.5 2.8,3.9 2,4 1,3.75 0.3,3 0,2 0.3,0.9 1,0.25 2,0 3,0.15 3.7,0.6"],
    "f": ["3.8,5.8 3.2,6 2.4,6 1.8,5.6 1.6,4.8 1.6,0", "0.4,4 3.2,4"], "g": ["@2,2,2,2,0,360", "4,4 4,-0.8", "@2,-0.8,2,1.2,0,-180"],
    "h": ["0,6 0,0", "0,2.4 0.4,3.4 1.2,3.9 2,4 2.8,3.9 3.6,3.4 4,2.4 4,0"], "i": ["2,4 2,0", "2,5.3 2,5.5"],
    "j": ["2.5,4 2.5,-1", "@1.25,-1,1.25,1,0,-180", "2.5,5.3 2.5,5.5"], "k": ["0,6 0,0", "3.6,4 0,1.4", "1.3,2.3 3.8,0"], "l": ["2,6 2,0"],
    "m": ["0,4 0,0", "0,3 0.5,3.8 1,4 1.5,3.8 2,3 2,0", "2,3 2.5,3.8 3,4 3.5,3.8 4,3 4,0"],
    "n": ["0,4 0,0", "0,2.4 0.4,3.4 1.2,3.9 2,4 2.8,3.9 3.6,3.4 4,2.4 4,0"], "o": ["@2,2,2,2,0,360"], "p": ["0,4 0,-2", "@2,2,2,2,180,540"],
    "q": ["4,4 4,-2", "@2,2,2,2,0,360"], "r": ["0,4 0,0", "0,2.2 0.6,3.4 1.6,4 2.6,4 3.4,3.6"],
    "s": ["3.8,3.4 3,3.9 2,4 1,3.9 0.3,3.4 0.3,2.6 1,2.2 3,1.8 3.7,1.4 3.7,0.6 3,0.1 2,0 1,0.1 0.2,0.6"],
    "t": ["1.6,5.5 1.6,0.8 2,0.1 2.6,0 3.4,0.2", "0.4,4 3.2,4"], "u": ["0,4 0,1.6 0.4,0.6 1.2,0.1 2,0 2.8,0.1 3.6,0.6 4,1.6", "4,4 4,0"],
    "v": ["0,4 2,0 4,4"], "w": ["0,4 1,0 2,3 3,0 4,4"], "x": ["0,4 4,0", "0,0 4,4"], "y": ["0,4 2,0", "4,4 1.2,-2"], "z": ["0,4 4,4 0,0 4,0"],
    ".": ["1.9,0.1 2.1,0.1"], ",": ["2.1,0.3 2.1,0 1.5,-1"], ":": ["2,0.2 2,0.4", "2,3.6 2,3.8"], ";": ["2,3.6 2,3.8", "2.1,0.3 2.1,0 1.5,-1"],
    "-": ["0.8,3 3.2,3"], "_": ["0,-0.6 4,-0.6"], "+": ["0.6,3 3.4,3", "2,1.6 2,4.4"], "/": ["0,0 4,6"], "\\": ["0,6 4,0"],
    "(": ["3,6.5 2,5.2 1.6,3 2,0.8 3,-0.5"], ")": ["1,6.5 2,5.2 2.4,3 2,0.8 1,-0.5"], "[": ["3,6.5 1.5,6.5 1.5,-0.5 3,-0.5"],
    "]": ["1,6.5 2.5,6.5 2.5,-0.5 1,-0.5"], "=": ["0.6,4 3.4,4", "0.6,2 3.4,2"], "%": ["0,0 4,6", "@0.9,5,0.9,1,0,360", "@3.1,1,0.9,1,0,360"],
    "#": ["1.2,0 1.8,6", "2.6,0 3.2,6", "0.4,4.2 4,4.2", "0.1,1.8 3.6,1.8"],
    "&": ["4,0 0.8,4.2 0.8,5.2 1.5,6 2.5,6 3.1,5.3 3,4.4 0.4,2.3 0.2,1.2 0.9,0.2 2,0 3.2,0.6 4,2"],
    "*": ["2,1.5 2,4.5", "0.7,2.25 3.3,3.75", "0.7,3.75 3.3,2.25"], "!": ["2,6 2,1.8", "2,0.1 2,0.3"],
    "?": ["0.3,4.7 0.8,5.6 2,6 3.2,5.6 3.7,4.6 3.3,3.6 2,2.8 2,1.8", "2,0.1 2,0.3"], "'": ["2,6 2,4.5"], "\"": ["1.4,6 1.4,4.5", "2.6,6 2.6,4.5"],
    "<": ["4,5 0,3 4,1"], ">": ["0,5 4,3 0,1"], "@": ["@2,3,2,3,0,330", "@2.2,3,0.9,1.2,0,360"], "°": ["@2,5,0.7,0.7,0,360"],
    "~": ["0,3 0.7,3.7 1.5,3.8 2.5,3.2 3.3,3.3 4,4"], "|": ["2,6.5 2,-1"], "^": ["0.5,4 2,6 3.5,4"],
    "$": ["@2,4.5,2,1.3,20,270", "@2,1.7,2,1.3,90,-160", "2,6.6 2,-0.6"], "µ": ["0,4 0,-2", "0,1.6 0.4,0.6 1.2,0.1 2,0 2.8,0.1 3.6,0.6 4,1.6", "4,4 4,0"],
    "Ω": ["0,0 1.4,0 1.4,0.8 0.4,2 0,3.2 0.4,4.6 1.2,5.6 2,6 2.8,5.6 3.6,4.6 4,3.2 3.6,2 2.6,0.8 2.6,0 4,0"],
};
const glyphCache = new Map();
function glyph(ch) {
    if (glyphCache.has(ch))
        return glyphCache.get(ch);
    const spec = FONT[ch] || FONT[ch.toUpperCase()] || ["0,0 4,0 4,6 0,6 0,0"];
    const out = [];
    for (const s of spec) {
        if (s[0] === "@") {
            const [cx, cy, rx, ry, a1, a2] = s.slice(1).split(",").map(Number);
            const n = Math.max(8, Math.ceil(Math.abs(a2 - a1) / 10)), pts = [];
            for (let k = 0; k <= n; k++) {
                const a = (a1 + (a2 - a1) * k / n) * Math.PI / 180;
                pts.push([cx + rx * Math.cos(a), cy + ry * Math.sin(a)]);
            }
            out.push(pts);
        }
        else
            out.push(s.trim().split(/\s+/).map(p => p.split(",").map(Number)));
    }
    glyphCache.set(ch, out);
    return out;
}
// A text in board millimetres (Y down): [layer, x, y, h, w, stroke, rot, hj, vj, mirrored, text, comp].
function textPolylines(t) {
    const H = t[3], u = H / 6, ux = (t[4] > 0 ? t[4] : H * 2 / 3) / 4, th = t[6] * Math.PI / 180, c = Math.cos(th), s = Math.sin(th);
    const n = [...t[10]].length, TW = (n - 1) * 6 * ux + 4 * ux;
    const ox = t[7] === "left" ? 0 : t[7] === "right" ? -TW : -TW / 2, oy = t[8] === "bottom" ? 0 : t[8] === "top" ? -6 * u : -3 * u;
    const mir = t[9] ? -1 : 1, out = [];
    [...t[10]].forEach((ch, i) => {
        for (const pl of glyph(ch))
            out.push(pl.map(([gx, gy]) => {
                const lx = (ox + (gx + 6 * i) * ux) * mir, ly = -(oy + gy * u);
                return [t[1] + lx * c + ly * s, t[2] - lx * s + ly * c];
            }));
    });
    return out;
}
// ---- core/units.ts
// ================================================================== units: millimetres or mil (Q), as in Altium
const MIL_MM = 0.0254;
let UNIT = (() => { try {
    return localStorage.getItem("fenolite.view.unit") === "mil" ? "mil" : "mm";
}
catch (e) {
    return "mm";
} })();
function fmtLen(mm) { return UNIT === "mil" ? `${(mm / MIL_MM).toFixed(2)} mil` : `${mm.toFixed(3)} mm`; }
function fmtNm(nm) { return fmtLen(nm / 1e6); }
function fmtXY(a, b) { return UNIT === "mil" ? `${(a / MIL_MM).toFixed(2)}, ${(b / MIL_MM).toFixed(2)} mil` : `${a.toFixed(3)}, ${b.toFixed(3)} mm`; } // a position (c0301)
function fmtPair(a, b) { return UNIT === "mil" ? `${(a / MIL_MM).toFixed(2)} × ${(b / MIL_MM).toFixed(2)} mil` : `${a.toFixed(3)} × ${b.toFixed(3)} mm`; }
function setUnit(u) {
    UNIT = u;
    refreshToolbar();
    refreshStatus();
    try {
        localStorage.setItem("fenolite.view.unit", u);
    }
    catch (e) { /* the choice is kept for this page only */ }
    if (!S)
        return;
    refreshInspector();
    refreshSummary(); // c0301: the selection's model is built again in the new unit
    if (st.mouse)
        showCoord(st.mouse[0], st.mouse[1]);
    buildLibList();
    draw();
}
// ---- panels/status-bar.tsx
// The status bar (c0300, design decision 6), left to right: the cursor position in the page unit, the grid pitch
// when a grid is drawn, the zoom, the current layer, the selection, then the unit and the live state. The file's
// digest is not here: it is in "About this document". The spans keep their ids (coord, zoomv, cur, live): the
// tools write the cursor, the measure and the live state into them as they always did.
function StatusBar() {
    return preact.h(preact.Fragment, null,
        preact.h("span", { class: "sItem sCoord" },
            preact.h(Icon, { name: "target", size: 12 }),
            preact.h("span", { id: "coord" }, "x \u2014 y \u2014")),
        preact.h("span", { class: "sItem", id: "gridv", hidden: true }),
        preact.h("span", { class: "sItem", id: "zoomv" }),
        preact.h("span", { class: "sItem", id: "cur" }),
        preact.h("span", { class: "sItem sSel", id: "selv" }),
        preact.h("span", { class: "sSpacer" }),
        preact.h("span", { class: "sItem", id: "unitv", title: "Page unit (Q)" }),
        preact.h("span", { class: "sItem sLive", id: "live" }));
}
preact.render(preact.h(StatusBar, null), $("status"));
function statusText(id, text) { const el = $(id); if (!el)
    return; el.textContent = text; el.hidden = !text; }
function refreshStatus() {
    statusText("unitv", S && S.kind !== "table" ? (UNIT === "mm" ? "Millimetres" : "Mil") : "");
    statusText("gridv", S && isSch() && S.sheet.grid ? `Grid ${fmtLen(S.sheet.grid)}` : "");
    let sel = "";
    if (S && isSch())
        sel = SCH.selComp >= 0 ? `Part ${S.comps[SCH.selComp].ref}` : SCH.selNet >= 0 ? `Net ${S.nets[SCH.selNet].name || "(no name)"}` : "";
    else if (S && !S.kind && S.comps) {
        if (st.selComp >= 0)
            sel = `Part ${S.comps[st.selComp].ref}`;
        else if (st.selNet >= 0)
            sel = `Net ${S.nets[st.selNet]}`;
        else if (st.query && (st.query.comps.length || st.query.prims.size))
            sel = `Filter: ${st.query.comps.length} part(s) · ${st.query.prims.size} item(s)`;
    }
    statusText("selv", sel);
}
// ---- board/decode.ts
// <decodeV1> c0182: a compact board scene (fenolite.view_scene.v1, view/compact.py) back to its v0 primitives
function decodeV1(sc) {
    const p = sc.p1;
    if (!p)
        return sc;
    const D = p.D, FIXED = { c: 1, s: 2, a: 3 }, last = new Map(), prims = new Array(p.K.length);
    let at = 0, cx = 0, cy = 0;
    const pts = (n, x, y) => { const out = new Array(2 * n); for (let i = 0; i < n; i++) {
        x += D[at++];
        y += D[at++];
        out[2 * i] = x;
        out[2 * i + 1] = y;
    } return out; };
    for (let k = 0; k < p.K.length; k++) {
        const kind = p.K[k];
        let v;
        if (kind === "p" || kind === "o" || kind === "h") {
            const count = D[at++];
            v = [];
            let rx = cx, ry = cy;
            for (let r = 0; r < count; r++) {
                const ring = pts(D[at++], rx, ry);
                if (ring.length) {
                    rx = ring[0];
                    ry = ring[1];
                    if (r === 0) {
                        cx = rx;
                        cy = ry;
                    }
                }
                v.push(ring);
            }
        }
        else if (kind === "l") {
            const n = D[at++], w = D[at++];
            const f = pts(n, cx, cy);
            cx = f[0];
            cy = f[1];
            v = [w, ...f];
        }
        else {
            const f = pts(FIXED[kind], cx, cy);
            cx = f[0];
            cy = f[1];
            f.push(D[at++]);
            v = f;
        }
        const s = p.S[k], n = (last.get(s) || 0) + p.SN[k];
        last.set(s, n);
        const t = p.strings[s];
        prims[k] = [p.layers[p.L[k]], kind, v, p.N[k], p.C[k], t.includes("\u0001") ? t.replace("\u0001", String(n)) : t];
    }
    delete sc.p1;
    sc.prims = prims;
    sc.schema = "fenolite.view_scene.v0";
    return sc;
}
// </decodeV1>
// ---- board/scene.ts
async function unpackScene(v) {
    if (typeof v !== "string")
        return v;
    const bin = Uint8Array.from(atob(v.slice(3)), c => c.charCodeAt(0));
    const text = await new Response(new Blob([bin]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
    return JSON.parse(text);
}
function primToMM(pr, f) {
    const d = pr[2];
    if (pr[1] === "p" || pr[1] === "o" || pr[1] === "h")
        pr[2] = d.map(r => r.map(f));
    else
        pr[2] = d.map(f);
    if (pr[1] === "a")
        pr.push(arcOf(pr[2]));
}
function diffToMM(sc) {
    const D = sc.diff;
    if (!D)
        return;
    const f = v => v * MM;
    for (const pr of [...(D.added || []), ...(D.removed || [])])
        primToMM(pr, f);
    for (const m of D.moved || []) {
        m.from = m.from.map(f);
        m.to = m.to.map(f);
    }
    for (const c of D.changes)
        if (c.box)
            c.box = c.box.map(f);
}
function toMM(scene) {
    decodeV1(scene);
    if (scene.mm)
        return scene;
    scene.mm = true;
    diffToMM(scene);
    checkToMM(scene);
    rolesToMM(scene);
    for (const p of scene.pads || []) {
        p.x *= MM;
        p.y *= MM;
    }
    const f = v => v * MM;
    for (const pr of scene.prims)
        primToMM(pr, f);
    for (const t of scene.texts)
        for (const k of [1, 2, 3, 4, 5])
            t[k] = t[k] * MM;
    for (const c of scene.comps) {
        c.x *= MM;
        c.y *= MM;
        if (c.bbox)
            c.bbox = c.bbox.map(f);
    }
    for (const r of scene.board) {
        r.points = r.points.map(f);
        r.mids = r.mids.map(m => m ? m.map(f) : null);
    }
    scene.bounds = scene.bounds.map(f);
    scene.board3d.thickness *= MM;
    for (const b of scene.bodies) {
        b.ring = b.ring.map(f);
        b.z0 *= MM;
        b.z1 *= MM;
        if (b.zs)
            b.zs = b.zs.map(f);
    }
    for (const o of scene.overlays || []) {
        o.pts = o.pts.map(p => p.map(f));
        if (o.bbox)
            o.bbox = o.bbox.map(f);
    }
    return scene;
}
// ---- board/geometry.ts
// an arc through three points: centre, radius, start and end angles, and the direction (canvas angles, Y down)
function arcOf(d) {
    const [x1, y1, x2, y2, x3, y3] = d, D = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2));
    if (Math.abs(D) < 1e-12)
        return null;
    const q1 = x1 * x1 + y1 * y1, q2 = x2 * x2 + y2 * y2, q3 = x3 * x3 + y3 * y3;
    const cx = (q1 * (y2 - y3) + q2 * (y3 - y1) + q3 * (y1 - y2)) / D, cy = (q1 * (x3 - x2) + q2 * (x1 - x3) + q3 * (x2 - x1)) / D;
    const a1 = Math.atan2(y1 - cy, x1 - cx), am = Math.atan2(y2 - cy, x2 - cx), a3 = Math.atan2(y3 - cy, x3 - cx), T = 2 * Math.PI;
    const d13 = ((a3 - a1) % T + T) % T, d1m = ((am - a1) % T + T) % T;
    return { cx, cy, r: Math.hypot(x1 - cx, y1 - cy), a1, a3, ccw: d1m > d13 };
}
function ringSamples(ring) {
    const p = ring.points, out = [];
    for (let i = 0; i < p.length; i += 2) {
        const j = (i + 2) % p.length, m = ring.mids[i / 2];
        out.push([p[i], p[i + 1]]);
        if (m) {
            const a = arcOf([p[i], p[i + 1], m[0], m[1], p[j], p[j + 1]]);
            if (a) {
                let span = ((a.a3 - a.a1) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI);
                if (a.ccw)
                    span -= 2 * Math.PI;
                for (let k = 1; k < 16; k++) {
                    const t = a.a1 + span * k / 16;
                    out.push([a.cx + a.r * Math.cos(t), a.cy + a.r * Math.sin(t)]);
                }
            }
        }
    }
    return out;
}
function boardPath() { const bp = new P2D(); for (const r of S.board) {
    const pts = ringSamples(r);
    pts.forEach((q, k) => k ? bp.lineTo(q[0], q[1]) : bp.moveTo(q[0], q[1]));
    bp.closePath();
} return bp; }
// ---- board/cache.ts
let qCache = new Map(), cache = null, netCache = new Map(), compCache = new Map(), textCache = new Map(), byLayer = new Map();
function lighten(hex, f) {
    const n = parseInt(hex.slice(1), 16);
    let r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    r = Math.round(r + (255 - r) * f);
    g = Math.round(g + (255 - g) * f);
    b = Math.round(b + (255 - b) * f);
    return `rgb(${r},${g},${b})`;
}
function ringPath(p, flat) { p.moveTo(flat[0], flat[1]); for (let i = 2; i < flat.length; i += 2)
    p.lineTo(flat[i], flat[i + 1]); p.closePath(); }
function strokePath(c, w) { let p = c.strokes.get(w); if (!p) {
    p = new P2D();
    c.strokes.set(w, p);
} return p; }
function addPrim(c, pr) {
    const k = pr[1], d = pr[2];
    if (k === "s") {
        const p = strokePath(c, d[4]);
        p.moveTo(d[0], d[1]);
        p.lineTo(d[2], d[3]);
        if (d[0] === d[2] && d[1] === d[3])
            p.lineTo(d[2] + 1e-4, d[3]);
    }
    else if (k === "a") {
        const a = pr[6], p = strokePath(c, d[6]);
        if (!a) {
            p.moveTo(d[0], d[1]);
            p.lineTo(d[4], d[5]);
        }
        else {
            p.moveTo(d[0], d[1]);
            p.arc(a.cx, a.cy, a.r, a.a1, a.a3, a.ccw);
        }
    }
    else if (k === "l") {
        const p = strokePath(c, d[0]);
        p.moveTo(d[1], d[2]);
        for (let i = 3; i < d.length; i += 2)
            p.lineTo(d[i], d[i + 1]);
        if (d.length === 3)
            p.lineTo(d[1] + 1e-4, d[2]);
    }
    else if (k === "c") {
        c.fill.moveTo(d[0] + d[2], d[1]);
        c.fill.arc(d[0], d[1], d[2], 0, 2 * Math.PI);
        c.fill.closePath();
    }
    else if (k === "p") {
        for (const r of d)
            ringPath(c.fill, r);
    }
    else if (k === "o") {
        for (const r of d)
            ringPath(c.outline, r);
    }
    else if (k === "h") {
        for (const r of d) {
            ringPath(c.hatch, r);
            for (let i = 0; i < r.length; i += 2) { // c0183: a keep-out or a finding, hatched
                c.hb[0] = Math.min(c.hb[0], r[i]);
                c.hb[1] = Math.min(c.hb[1], r[i + 1]);
                c.hb[2] = Math.max(c.hb[2], r[i]);
                c.hb[3] = Math.max(c.hb[3], r[i + 1]);
            }
        }
    }
    c.n++;
}
function newCache() { return { fill: new P2D(), strokes: new Map(), outline: new P2D(), hatch: new P2D(), hb: [1e9, 1e9, -1e9, -1e9], n: 0 }; }
function bboxOf(pr) {
    const d = pr[2];
    switch (pr[1]) {
        case "s": return [Math.min(d[0], d[2]) - d[4] / 2, Math.min(d[1], d[3]) - d[4] / 2, Math.max(d[0], d[2]) + d[4] / 2, Math.max(d[1], d[3]) + d[4] / 2];
        case "a": {
            const a = pr[6], w = d[6] / 2;
            if (!a)
                return [Math.min(d[0], d[4]) - w, Math.min(d[1], d[5]) - w, Math.max(d[0], d[4]) + w, Math.max(d[1], d[5]) + w];
            return [a.cx - a.r - w, a.cy - a.r - w, a.cx + a.r + w, a.cy + a.r + w];
        }
        case "c": return [d[0] - d[2], d[1] - d[2], d[0] + d[2], d[1] + d[2]];
        case "l": {
            let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
            for (let i = 1; i < d.length; i += 2) {
                x0 = Math.min(x0, d[i]);
                x1 = Math.max(x1, d[i]);
                y0 = Math.min(y0, d[i + 1]);
                y1 = Math.max(y1, d[i + 1]);
            }
            return [x0 - d[0] / 2, y0 - d[0] / 2, x1 + d[0] / 2, y1 + d[0] / 2];
        }
        default: {
            let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
            for (const ring of d)
                for (let i = 0; i < ring.length; i += 2) {
                    x0 = Math.min(x0, ring[i]);
                    x1 = Math.max(x1, ring[i]);
                    y0 = Math.min(y0, ring[i + 1]);
                    y1 = Math.max(y1, ring[i + 1]);
                }
            return [x0, y0, x1, y1];
        }
    }
}
function buildCaches() {
    qCache = new Map();
    cache = new Map();
    netCache = new Map();
    compCache = new Map();
    textCache = new Map();
    byLayer = new Map();
    for (const l of S.layers) {
        cache.set(l.id, newCache());
        byLayer.set(l.id, []);
        textCache.set(l.id, { strokes: new Map(), n: 0 });
    }
    for (const pr of S.prims) {
        const c = cache.get(pr[0]);
        if (c) {
            addPrim(c, pr);
            byLayer.get(pr[0]).push([pr, bboxOf(pr)]);
        }
    }
    for (const t of S.texts) {
        const tc = textCache.get(t[0]);
        if (!tc)
            continue;
        tc.n++;
        const p = strokePath(tc, Math.max(t[5], 0.05));
        for (const pl of textPolylines(t)) {
            p.moveTo(pl[0][0], pl[0][1]);
            for (let k = 1; k < pl.length; k++)
                p.lineTo(pl[k][0], pl[k][1]);
            if (pl.length === 1)
                p.lineTo(pl[0][0] + 1e-4, pl[0][1]);
        }
    }
}
function selCache(map, key, test) {
    if (map.has(key))
        return map.get(key);
    const m = new Map();
    for (const l of S.layers)
        m.set(l.id, newCache());
    for (const pr of S.prims)
        if (test(pr)) {
            const c = m.get(pr[0]);
            if (c)
                addPrim(c, pr);
        }
    map.set(key, m);
    return m;
}
// ---- core/viewport.ts
// ================================================================== 2D view
let W = 0, H = 0, dpr = 1;
function setDpr(v) { dpr = v; }
function measure() {
    const r = cv.getBoundingClientRect();
    dpr = window.devicePixelRatio || 1;
    W = r.width || W;
    H = r.height || H;
    cv.width = Math.max(1, Math.round(W * dpr));
    cv.height = Math.max(1, Math.round(H * dpr));
}
let fitted = false;
function setFitted(v) { fitted = v; }
function resize() { measure(); if (st.mode3d)
    resize3D(); if (S && !fitted)
    fit();
else
    draw(); }
new ResizeObserver(resize).observe($("wrap"));
function m() { return view.mirror ? -1 : 1; }
function w2s(x, y) { return [W / 2 + m() * (x - view.cx) * view.s, H / 2 + (y - view.cy) * view.s]; }
function s2w(X, Y) { return [view.cx + m() * (X - W / 2) / view.s, view.cy + (Y - H / 2) / view.s]; }
function worldTf(g) { (g || ctx).setTransform(dpr * m() * view.s, 0, 0, dpr * view.s, dpr * (W / 2 - m() * view.cx * view.s), dpr * (H / 2 - view.cy * view.s)); }
function fit(b) {
    if (!S || S.kind === "table")
        return;
    measure(); // a table (c0190) has no bounds
    b = b || S.bounds;
    const w = b[2] - b[0], h = b[3] - b[1];
    view.cx = (b[0] + b[2]) / 2;
    view.cy = (b[1] + b[3]) / 2;
    view.s = Math.max(0.2, Math.min(Math.max(W - 40, 60) / Math.max(w, 1), Math.max(H - 40, 60) / Math.max(h, 1)));
    fitted = W > 100 && H > 100;
    draw();
}
// ---- board/draw.ts
const VIEWL = id => id.startsWith("View.");
function activeSide() { return view.mirror ? "bottom" : "top"; }
function order() {
    const L = S.layers.filter(l => vis.get(l.id));
    if (st.single)
        return L.filter(l => l.id === st.cur || l.id === "View.Drill" || l.id === "View.Outline").map(l => [l, 1]);
    const act = activeSide(), other = act === "top" ? "bottom" : "top";
    const both = L.filter(l => l.side === "both" && !VIEWL(l.id)), oth = L.filter(l => l.side === other), actL = L.filter(l => l.side === act), post = L.filter(l => VIEWL(l.id));
    if (act === "bottom")
        actL.reverse();
    let out = [...oth.map(l => [l, st.opac]), ...both.map(l => [l, 1]), ...actL.map(l => [l, 1]), ...post.map(l => [l, 1])];
    const ci = out.findIndex(e => e[0].id === st.cur);
    if (ci >= 0) {
        const [e] = out.splice(ci, 1);
        e[1] = 1;
        out.splice(out.length - post.length, 0, e);
    }
    return out;
}
function paintCache(g, c, lid, color, alpha, unit) {
    if (!c || !c.n)
        return;
    g.globalAlpha = alpha;
    if (lid === "View.Drill") {
        g.fillStyle = color;
        g.fill(c.fill, "nonzero");
        g.strokeStyle = color;
        g.lineCap = "round";
        for (const [w, p] of c.strokes) {
            g.lineWidth = Math.max(w, 1 / unit);
            g.stroke(p);
        }
        return;
    }
    g.fillStyle = color;
    g.fill(c.fill, "evenodd");
    g.strokeStyle = color;
    g.lineCap = "round";
    g.lineJoin = "round";
    for (const [w, p] of c.strokes) {
        g.lineWidth = Math.max(w, 1 / unit);
        g.stroke(p);
    }
    if (lid === "View.ZoneOutline" || lid === "View.ZoneEdge")
        g.setLineDash([6 / unit, 4 / unit]);
    g.lineWidth = 1 / unit;
    g.stroke(c.outline);
    g.setLineDash([]);
    if (c.hb[2] >= c.hb[0]) {
        const [x0, y0, x1, y1] = c.hb, step = 8 / unit; // hatched rings: 45° lines inside, a solid edge
        g.save();
        g.clip(c.hatch, "evenodd");
        g.lineWidth = 1 / unit;
        g.beginPath();
        for (let t = x0 - (y1 - y0); t <= x1; t += step) {
            g.moveTo(t, y0);
            g.lineTo(t + (y1 - y0), y1);
        }
        g.stroke();
        g.restore();
        g.lineWidth = 1.5 / unit;
        g.stroke(c.hatch);
    }
}
function paintTexts(g, lid, color, alpha, unit) {
    const tc = textCache.get(lid);
    if (!tc || !tc.n)
        return;
    g.globalAlpha = alpha;
    g.strokeStyle = color;
    g.lineCap = "round";
    g.lineJoin = "round";
    for (const [w, p] of tc.strokes) {
        g.lineWidth = Math.max(w, 0.6 / unit);
        g.stroke(p);
    }
}
// ---- net emphasis (c0301, design decision 4): a picked net, part or filter result is drawn in its own layer
// colours at full opacity with a 1.5 px outline in the --emphasis token, never lightened; its zone fills at 0.55
// with the outline, so its tracks and pads stay readable over its pour. The rest dims by the highlight mode.
let EMPHASIS = "", EMPHASIS_KEY = "";
function emphasisColor() {
    const key = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: light)").matches ? "l" : "d");
    if (!EMPHASIS || key !== EMPHASIS_KEY) {
        EMPHASIS_KEY = key;
        EMPHASIS = getComputedStyle(document.documentElement).getPropertyValue("--emphasis").trim() || "#ffffff";
    }
    return EMPHASIS;
}
const ZONE_FILL_ALPHA = 0.55;
const isZoneFill = pr => pr[1] === "p" && pr[4] < 0 && pr[3] >= 0;
function paintEmphasis(g, c, lid, color, unit, zone) {
    if (!c || !c.n)
        return;
    if (VIEWL(lid)) {
        paintCache(g, c, lid, color, 1, unit);
        return;
    }
    const em = emphasisColor(), w = 1.5 / unit;
    g.globalAlpha = 1;
    g.strokeStyle = em;
    g.lineCap = "round";
    g.lineJoin = "round";
    if (zone) {
        paintCache(g, c, lid, color, ZONE_FILL_ALPHA, unit);
        g.globalAlpha = 1;
        g.strokeStyle = em;
        g.lineWidth = w;
        g.stroke(c.fill);
        return;
    }
    g.lineWidth = 2 * w;
    g.stroke(c.fill); // the outline: half of it under the fill, half outside
    for (const [sw, p] of c.strokes) {
        g.lineWidth = Math.max(sw, 1 / unit) + 2 * w;
        g.stroke(p);
    }
    paintCache(g, c, lid, color, 1, unit);
}
function paintPicked(map, key, test, ord) {
    const zones = selCache(map, "z:" + key, pr => test(pr) && isZoneFill(pr)), rest = selCache(map, key, pr => test(pr) && !isZoneFill(pr));
    for (const [l] of ord)
        paintEmphasis(ctx, zones.get(l.id), l.id, l.color, view.s, true);
    for (const [l] of ord)
        paintEmphasis(ctx, rest.get(l.id), l.id, l.color, view.s, false);
}
function draw() {
    if (S && S.kind === "table")
        return;
    if (S && S.kind === "schematic")
        return drawSch();
    if (!S || st.mode3d)
        return;
    const th = S.theme || {};
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.fillStyle = th.background || "#15171b";
    ctx.fillRect(0, 0, cv.width, cv.height);
    worldTf();
    ctx.globalAlpha = 1;
    ctx.fillStyle = th.board || "#050505";
    ctx.fill(boardPath(), "evenodd");
    const qy = st.query && st.query.prims.size ? st.query : null, picked = st.selNet >= 0 || st.selComp >= 0;
    const ord = order(), sel = picked || !!qy, other = HL_ALPHA[st.hl] ?? HL_ALPHA.dim;
    const dim = S.diff && st.diff && S.diff.kind === "board" ? 0.35 : 1; // c0184: the board steps back while the changes are shown
    for (const [l, a00] of ord) {
        const a0 = a00 * dim, a = a0 * (l.alpha ?? 1);
        paintCache(ctx, cache.get(l.id), l.id, l.color, sel ? a * other : a, view.s);
        if (view.s * 0.4 > 1)
            paintTexts(ctx, l.id, l.color, sel ? a * other : a, view.s);
    }
    paintRoleCopper(ord, (sel ? other : 1) * dim); // c0305: role copper in its role colour, under a pick's emphasis
    if (qy) {
        paintPicked(qCache, qy.text, pr => qy.prims.has(pr), ord);
        ctx.globalAlpha = 1;
        ctx.strokeStyle = emphasisColor();
        ctx.lineWidth = 1 / view.s;
        for (const ci of qy.comps.slice(0, 2000)) {
            const b = S.comps[ci].bbox;
            if (b)
                ctx.strokeRect(b[0] - 0.2, b[1] - 0.2, b[2] - b[0] + 0.4, b[3] - b[1] + 0.4);
        }
    }
    if (picked) {
        if (st.selNet >= 0)
            paintPicked(netCache, st.selNet, pr => pr[3] === st.selNet, ord);
        else
            paintPicked(compCache, st.selComp, pr => pr[4] === st.selComp, ord);
        if (st.selComp >= 0 && S.comps[st.selComp].bbox) {
            const b = S.comps[st.selComp].bbox;
            ctx.globalAlpha = 1;
            ctx.strokeStyle = emphasisColor();
            ctx.lineWidth = 1.5 / view.s;
            ctx.setLineDash([5 / view.s, 3 / view.s]);
            ctx.strokeRect(b[0] - 0.3, b[1] - 0.3, b[2] - b[0] + 0.6, b[3] - b[1] + 0.6);
            ctx.setLineDash([]);
        }
    }
    if (VARIANT && S.variants) {
        worldTf();
        ctx.globalAlpha = 0.6;
        ctx.fillStyle = (S.theme || {}).board || "#050505";
        for (const c of S.comps)
            if (c.bbox && notFitted(c.ref)) {
                const b = c.bbox;
                ctx.fillRect(b[0], b[1], b[2] - b[0], b[3] - b[1]);
            }
        drawVariantMarks(S.comps.map(c => [c.ref, c.bbox]));
    }
    drawDiff();
    drawOverlays();
    drawCheck();
    drawRoles();
    drawEdge();
    drawMarks();
    drawMeasure();
    linkLater();
    $("zoomv").textContent = `Zoom ${view.s.toFixed(1)} px/mm`;
    refreshStatus();
}
// ---- board/diff.ts
// ================================================================== changes since an older revision (c0184)
const DIFF_COLOR = { added: "#35e06b", removed: "#ff3cf0", moved: "#ffb020", changed: "#ffb020", zone: "#40c0ff", net: "#ffb020" };
function drawDiff() {
    const D = S.diff;
    if (!D || !st.diff || D.kind !== "board")
        return;
    if (!D.cache) {
        D.cache = { added: newCache(), removed: newCache() };
        for (const pr of D.added)
            addPrim(D.cache.added, pr);
        for (const pr of D.removed)
            addPrim(D.cache.removed, pr);
    }
    worldTf();
    paintCache(ctx, D.cache.removed, "diff", DIFF_COLOR.removed, 0.85, view.s);
    paintCache(ctx, D.cache.added, "diff", DIFF_COLOR.added, 0.85, view.s);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = ctx.fillStyle = DIFF_COLOR.moved;
    ctx.lineWidth = 2 / view.s;
    for (const m of D.moved) {
        const [x0, y0] = m.from, [x1, y1] = m.to, a = Math.atan2(y1 - y0, x1 - x0), h = 10 / view.s;
        ctx.beginPath();
        ctx.arc(x0, y0, 3 / view.s, 0, 2 * Math.PI);
        ctx.fill();
        ctx.beginPath();
        ctx.moveTo(x0, y0);
        ctx.lineTo(x1, y1);
        ctx.stroke();
        if (Math.hypot(x1 - x0, y1 - y0) > 0) {
            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x1 - h * Math.cos(a - 0.4), y1 - h * Math.sin(a - 0.4));
            ctx.lineTo(x1 - h * Math.cos(a + 0.4), y1 - h * Math.sin(a + 0.4));
            ctx.closePath();
            ctx.fill();
        }
    }
}
function drawSchDiff() {
    const D = S.diff;
    if (!D || !st.diff)
        return;
    ctx.globalAlpha = 1;
    ctx.lineWidth = 2 / view.s;
    ctx.setLineDash([6 / view.s, 3 / view.s]);
    for (const c of D.changes)
        if (c.box) {
            const b = c.box, e = 1.5;
            ctx.strokeStyle = DIFF_COLOR[c.kind] || "#ffb020";
            ctx.strokeRect(b[0] - e, b[1] - e, b[2] - b[0] + 2 * e, b[3] - b[1] + 2 * e);
        }
    ctx.setLineDash([]);
}
// ---- panels/changes.tsx
// The Changes panel of `--compare` (c0184), a Preact component (change c0304): one row per change, coloured by
// its kind; a row with a box frames it.
function frameChange(b) { const m = Math.max(b[2] - b[0], b[3] - b[1], 1) * 0.6; fit([b[0] - m, b[1] - m, b[2] + m, b[3] + m]); }
function ChangesPanel({ changes }) {
    return preact.h(preact.Fragment, null, changes.map(c => (preact.h("div", { class: "navi", onClick: c.box ? () => frameChange(c.box) : undefined },
        preact.h("span", { class: "sw", style: `background:${DIFF_COLOR[c.kind] || "#888"}` }),
        ` ${c.text}`))));
}
function buildDiffList() {
    const box = $("diffList"), D = S && S.diff;
    showSection("changes", !!D, D ? D.changes.length : undefined, D ? `Changes since ${D.old.name}` : "Changes");
    preact.render(D ? preact.h(ChangesPanel, { changes: D.changes }) : null, box);
}
// ---- review/check.ts
// ================================================================== check findings (c0188)
const SEV_COLOR = { error: "#ff4040", warning: "#ffb020", info: "#4da3ff" };
function checkToMM(sc) {
    const C = sc.check;
    if (!C || C.mm)
        return;
    C.mm = true;
    const f = v => v * MM;
    for (const x of C.findings) {
        if (x.at)
            x.at = x.at.map(f);
        if (x.box)
            x.box = x.box.map(f);
    }
}
function drawCheck() {
    const C = S.check;
    if (!C || !st.checks)
        return;
    if (!isSch())
        worldTf();
    ctx.globalAlpha = 1;
    for (let i = C.findings.length - 1; i >= 0; i--) {
        const x = C.findings[i]; // errors last, on top
        if (!x.at || (x.layer && vis.has(x.layer) && !vis.get(x.layer)))
            continue;
        const sel = i === st.selFinding, r = (sel ? 9 : 6) / view.s, [cx, cy] = x.at;
        ctx.strokeStyle = SEV_COLOR[x.severity] || "#cccccc";
        ctx.lineWidth = (sel ? 2.5 : 1.6) / view.s;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, 2 * Math.PI);
        for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
            ctx.moveTo(cx + dx * r * 0.6, cy + dy * r * 0.6);
            ctx.lineTo(cx + dx * r * 1.6, cy + dy * r * 1.6);
        }
        ctx.stroke();
        if (sel && x.box && (x.box[2] > x.box[0] || x.box[3] > x.box[1])) {
            const b = x.box, e = 2 / view.s;
            ctx.setLineDash([5 / view.s, 3 / view.s]);
            ctx.strokeRect(b[0] - e, b[1] - e, b[2] - b[0] + 2 * e, b[3] - b[1] + 2 * e);
            ctx.setLineDash([]);
        }
    }
}
function checkModel(i) {
    const x = S.check.findings[i], b = S.project_review?.binding;
    return imodel("finding", x.code, [findingSection(x, x.layer && !isSch() ? layerName(x.layer) : null)], { subtitle: [x.severity, x.stage].filter(Boolean).join(" · "), note: b && !b.matched ? `Historical report: ${b.note}` : "", target: { finding: i, comp: -1, net: -1 } });
}
function selectFinding(i) {
    const x = S.check.findings[i];
    st.selFinding = i;
    if (st.mode3d)
        set3D(false);
    if (x.layer && !isSch() && S.layers.some(l => l.id === x.layer)) {
        st.cur = x.layer;
        vis.set(x.layer, true);
        buildTabs();
    } // its layer, current
    if (x.at) {
        const b = x.box || [x.at[0], x.at[1], x.at[0], x.at[1]], m = Math.max(b[2] - b[0], b[3] - b[1], isSch() ? 10 : 6) * 0.8;
        fit([b[0] - m, b[1] - m, b[2] + m, b[3] + m]);
    }
    inspect(() => checkModel(i));
    buildMessages();
    draw();
}
// ---- roles/roles.ts
// ================================================================== net roles on the board (c0305)
// The role data of a board (scene.roles, fenolite.view_roles.v0): the reply of `fenolite roles --check` that
// `fenolite view --roles` or a roles run from a served page joined to the scene, its values unchanged. The role
// palette and glyphs and the idea of the view come from c0245-engineering-viewer (another session, superseded
// by the maintainer's decision of 2026-10-29 except for this view): seven colours chosen for Fenolite and told
// apart under simulated colour-vision deficiency, and a glyph for each role, so colour is never the only cue.
// The panel is panels/roles, the drawing roles/draw; the builders between the markers are pure and run under
// Node in tests/unit/view/test_page.py -k role.
// ---- roles model (c0305)
const ROLE_ORDER = ["power", "switch_node", "ground", "high_voltage", "gate", "kelvin", "signal"];
const ROLE_GLYPH = { power: "P", switch_node: "SW", ground: "G", kelvin: "K", gate: "GT", high_voltage: "HV", signal: "S" };
const ROLE_COLORS = {
    dark: { power: "#b8322c", switch_node: "#e28900", ground: "#0f6eb7", kelvin: "#7ec5a2", gate: "#d2a2f7", high_voltage: "#ffff89", signal: "#777777" },
    light: { power: "#631d1d", switch_node: "#b68500", ground: "#003a6a", kelvin: "#2f7157", gate: "#a357de", high_voltage: "#775b09", signal: "#8a8a8a" },
};
const GROUP_KIND = { hot: "switch_node", gate: "gate", kelvin: "kelvin" }; // the role colour of a group
const GROUP_LABEL = { hot: "Hot loop", gate: "Gate loop", kelvin: "Kelvin pair" };
const STATE_MARK = { confirmed: "✓", declared: "◆", inferred: "?" };
function roleName(kind) { return String(kind).replace(/_/g, " "); }
function amps(ma) { return `${+(ma / 1000).toFixed(3)} A`; }
function volts(mv) { return `${+(mv / 1000).toFixed(3)} V`; }
function roleLegend(data) {
    return ROLE_ORDER.filter(k => data && data.kinds && data.kinds[k]).map(k => ({ kind: k, glyph: ROLE_GLYPH[k], name: roleName(k), n: data.kinds[k] }));
}
function groupsOfNet(data, name, padNet) {
    return (data && data.groups || []).filter(g => g.net === name || g.pads.some(p => padNet(p) === name));
}
function roleSection(row, groups, f) {
    if (!row)
        return null;
    return isection("Role", [
        irow("Kind", row.kind), irow("State", row.state), irow("Rule", row.rule), irow("Confidence", row.confidence),
        row.pads && row.pads.length ? irow("Evidence pads", row.pads.join(", ")) : null,
        row.milliamps != null ? irow("Current", amps(row.milliamps)) : null,
        row.working_mv != null ? irow("Working voltage", volts(row.working_mv)) : null,
        row.sensitive ? irow("Sensitive", "yes") : null,
        groups.length ? irow("Groups", groups.map(g => `${g.name} (${(GROUP_LABEL[g.type] || g.type).toLowerCase()})`).join(", ")) : null,
    ]);
}
function groupSection(g, f) {
    return isection(GROUP_LABEL[g.type] || "Group", [
        irow("Name", g.name), irow("Origin", g.origin), irow("Rule", g.rule), irow("Confidence", g.confidence), irow("Pads", g.pads.join(", ")),
        g.net ? irow("Net", g.net) : null,
        g.area_nm2 != null ? irow("Loop area", f.area(g.area_nm2 / 1e12)) : null,
        g.bound_nm2 != null ? irow("Placement bound", f.area(g.bound_nm2 / 1e12)) : null,
        g.ratio_permille != null ? irow("Area to bound", `${(g.ratio_permille / 1000).toFixed(2)}`) : null,
    ]);
}
// ---- end roles model
const ROLES_KEY = "fenolite.view.roles";
const ROLE_VIEW = (() => {
    const on = { colors: true, loops: true, kelvin: true, findings: true };
    try {
        return { ...on, ...JSON.parse(localStorage.getItem(ROLES_KEY) || "{}") };
    }
    catch (e) {
        return on;
    }
})();
const ROLE_SEL = { group: -1, finding: -1, kind: "" };
function keepRoleView() { try {
    localStorage.setItem(ROLES_KEY, JSON.stringify(ROLE_VIEW));
}
catch (e) { /* kept for this page only */ } }
function rolesData() { return S && !S.kind && S.roles ? S.roles : null; }
function rolesToMM(sc) {
    const R = sc.roles;
    if (!R || R.mm)
        return;
    R.mm = true;
    const f = v => v * MM;
    for (const g of R.groups || [])
        g.points = (g.points || []).map(p => p.map(f));
    for (const x of R.findings || []) {
        if (x.at)
            x.at = x.at.map(f);
        if (x.box)
            x.box = x.box.map(f);
    }
}
function luminance(hex) { const n = parseInt(String(hex).slice(1, 7), 16); return Number.isNaN(n) ? 0 : (0.2126 * (n >> 16) + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255)) / 255; }
function roleTone() { return luminance((S && S.theme && S.theme.background) || "#15171b") > 0.5 ? "light" : "dark"; }
function roleColor(kind) { const set = ROLE_COLORS[roleTone()]; return set[kind] || set.signal; }
function roleRow(name) { const R = rolesData(); return R ? R.roles.find(r => r.net === name) || null : null; }
function roleOfNet(ni) { const R = rolesData(); return R && ni >= 0 ? R.roles.find(r => r.net_index === ni) || null : null; }
function padNet(label) { const p = S && S.pads ? S.pads.find(q => q.label === label) : null; return p ? p.net : null; }
function boardRole(ni) { const row = roleOfNet(ni); return row ? roleSection(row, groupsOfNet(rolesData(), row.net, padNet), FMT) : null; }
function groupModel(i) {
    const g = rolesData().groups[i];
    return imodel("group", g.name, [groupSection(g, FMT)], { subtitle: `${GROUP_LABEL[g.type] || g.type} · ${g.origin || ""}`, target: { group: i, comp: -1, net: -1 } });
}
function roleFindingModel(i) {
    const x = rolesData().findings[i];
    return imodel("finding", x.code, [findingSection(x, null)], { subtitle: [x.severity, x.stage].filter(Boolean).join(" · "), target: { roleFinding: i, comp: -1, net: -1 } });
}
function inferredRoles() { const R = rolesData(); return R ? R.roles.filter(r => r.state === "inferred").map(r => r.net) : []; }
function inferredGroups() { const R = rolesData(); return R ? R.groups.filter(g => g.origin === "inferred").map(g => g.name) : []; }
// ---- roles/draw.ts
// ================================================================== net roles drawn on the board (c0305)
// paintRoleCopper: the copper of each role net in its role colour, over the board and under a picked net's
// emphasis (signal nets stay as they are). drawRoles, after the check markers: hot loops hatched at 45° and gate
// loops at 135° through their pads with their name and area, Kelvin pairs as dashed sense lines from the
// element's pads to the receiver's, and the role findings as rings of their severity. Each overlay has its own
// hatch or dash, and the legend names every colour, so colour is never the only cue.
let roleCache = new Map();
const HALO = "#000000", LABEL_ZOOM = 12; // labels of the groups from 12 px/mm, or of the selected one
function resetRoleCache() { roleCache = new Map(); }
const copper = l => l.kind === "copper" || /\.Cu$/.test(l.id);
function paintRoleCopper(ord, alpha) {
    const R = rolesData();
    if (!R || !ROLE_VIEW.colors)
        return;
    for (const row of R.roles) {
        if (row.net_index < 0 || row.kind === "signal")
            continue;
        const m = selCache(roleCache, row.net_index, pr => pr[3] === row.net_index), color = roleColor(row.kind);
        for (const [l, a] of ord)
            if (copper(l))
                paintCache(ctx, m.get(l.id), l.id, color, Math.min(1, a) * alpha, view.s);
    }
}
function hatch(pts, angle, color, sel) {
    const u = 1 / view.s, path = new P2D();
    pts.forEach((p, k) => k ? path.lineTo(p[0], p[1]) : path.moveTo(p[0], p[1]));
    path.closePath();
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]), x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys), d = Math.max(x1 - x0, y1 - y0);
    ctx.save();
    ctx.clip(path);
    ctx.beginPath();
    const step = 7 * u, dir = angle === 45 ? 1 : -1;
    for (let t = -d; t <= 2 * d; t += step) {
        ctx.moveTo(x0 + t, y0);
        ctx.lineTo(x0 + t - dir * d, y0 + d);
    }
    ctx.globalAlpha = 0.55;
    ctx.strokeStyle = HALO;
    ctx.lineWidth = 2.6 * u;
    ctx.stroke(); // a dark halo: the hatch reads on its own role's copper
    ctx.globalAlpha = 0.95;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.2 * u;
    ctx.stroke();
    ctx.restore();
    ctx.lineJoin = "round";
    ctx.globalAlpha = 0.6;
    ctx.strokeStyle = HALO;
    ctx.lineWidth = (sel ? 5 : 3.6) * u;
    ctx.stroke(path);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = color;
    ctx.lineWidth = (sel ? 3 : 1.8) * u;
    ctx.stroke(path);
}
function label(x, y, text, color) {
    ctx.save();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const [X, Y] = w2s(x, y);
    ctx.font = "600 11px system-ui, sans-serif";
    const w = ctx.measureText(text).width;
    ctx.globalAlpha = 0.9;
    ctx.fillStyle = "#101216";
    ctx.fillRect(X - w / 2 - 5, Y - 9, w + 10, 18);
    ctx.globalAlpha = 1;
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.strokeRect(X - w / 2 - 5, Y - 9, w + 10, 18);
    ctx.fillStyle = "#f2f4f7";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(text, X, Y + 0.5);
    ctx.restore();
}
function drawRoles() {
    const R = rolesData();
    if (!R || (S && S.kind))
        return;
    worldTf();
    ctx.globalAlpha = 1;
    const u = 1 / view.s, labels = [];
    R.groups.forEach((g, i) => {
        const pts = g.points || [], sel = i === ROLE_SEL.group, color = roleColor(GROUP_KIND[g.type]);
        if (g.type === "kelvin") {
            if (!ROLE_VIEW.kelvin || pts.length < 4)
                return;
            const n = pts.length / 2, el = pts.slice(0, n), rx = pts.slice(n);
            ctx.strokeStyle = color;
            ctx.lineWidth = (sel ? 2.6 : 1.6) * u;
            ctx.setLineDash([4 * u, 3 * u]);
            ctx.beginPath();
            el.forEach((p, k) => { const q = rx[k] || rx[rx.length - 1]; ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]); });
            ctx.stroke();
            ctx.setLineDash([]);
            for (const p of el) {
                ctx.beginPath();
                ctx.arc(p[0], p[1], 4 * u, 0, 2 * Math.PI);
                ctx.stroke();
            }
            const c = el.reduce((a, p) => [a[0] + p[0] / el.length, a[1] + p[1] / el.length], [0, 0]);
            if (sel || view.s >= LABEL_ZOOM)
                labels.push([c[0], c[1] - 8 * u, `${ROLE_GLYPH.kelvin} ${g.name}`, color]);
            return;
        }
        if (!ROLE_VIEW.loops || pts.length < 3)
            return;
        hatch(pts, g.type === "hot" ? 45 : 135, color, sel);
        const c = pts.reduce((a, p) => [a[0] + p[0] / pts.length, a[1] + p[1] / pts.length], [0, 0]);
        const area = g.area_nm2 != null ? ` · ${fmtArea(g.area_nm2 / 1e12)}` : "";
        if (sel || view.s >= LABEL_ZOOM)
            labels.push([c[0], c[1], `${g.type === "hot" ? "⟲" : "⟳"} ${g.name}${area}`, color]);
    });
    if (ROLE_VIEW.findings)
        drawRoleFindings(R, u);
    for (const [x, y, text, color] of labels)
        label(x, y, text, color); // on top of the markers
}
function drawRoleFindings(R, u) {
    worldTf();
    for (let i = R.findings.length - 1; i >= 0; i--) {
        const x = R.findings[i];
        if (!x.at)
            continue;
        const sel = i === ROLE_SEL.finding, r = (sel ? 9 : 6) * u, [cx, cy] = x.at;
        ctx.globalAlpha = 1;
        ctx.strokeStyle = SEV_COLOR[x.severity] || "#cccccc";
        ctx.lineWidth = (sel ? 2.5 : 1.6) * u;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, 2 * Math.PI);
        ctx.moveTo(cx - r * 0.5, cy - r * 0.5);
        ctx.lineTo(cx + r * 0.5, cy + r * 0.5);
        ctx.moveTo(cx + r * 0.5, cy - r * 0.5);
        ctx.lineTo(cx - r * 0.5, cy + r * 0.5);
        ctx.stroke();
        if (sel && x.box && (x.box[2] > x.box[0] || x.box[3] > x.box[1])) {
            const b = x.box, e = 2 * u;
            ctx.setLineDash([5 * u, 3 * u]);
            ctx.strokeRect(b[0] - e, b[1] - e, b[2] - b[0] + 2 * e, b[3] - b[1] + 2 * e);
            ctx.setLineDash([]);
        }
    }
}
// ---- panels/messages.tsx
// The Messages panel of `--check` (c0188), a Preact component (change c0304): the notes, then the findings
// grouped by rule, errors first; a group opens on a click, a finding is selected on the drawing.
const MSG_ROWS = 300;
function toggleGroup(code, open) { if (open)
    st.msgOpen.delete(code);
else
    st.msgOpen.add(code); buildMessages(); }
function MessagesPanel({ check }) {
    const groups = new Map();
    check.findings.forEach((x, i) => { if (!groups.has(x.code))
        groups.set(x.code, []); groups.get(x.code).push(i); });
    const out = check.notes.map((note, k) => preact.h("div", { key: "t:" + k, class: "notes" }, note)); // keys: as in the Findings panel
    for (const [code, list] of groups) {
        const first = check.findings[list[0]], open = st.msgOpen.has(code) || groups.size === 1;
        out.push(preact.h("div", { key: "g:" + code, class: "navg", onClick: () => toggleGroup(code, open) },
            preact.h("span", { class: "sw", style: `display:inline-block;background:${SEV_COLOR[first.severity] || "#888"}` }),
            ` ${open ? "▾" : "▸"} ${code} (${list.length})`));
        if (!open)
            continue;
        for (const i of list.slice(0, MSG_ROWS)) {
            const x = check.findings[i]; // the title is the location as the panel always set it: "undefined" when there is none
            out.push(preact.h("div", { key: "f:" + i, class: "navi" + (i === st.selFinding ? " sel" : ""), title: String(x.where), onClick: () => selectFinding(i) },
                String(x.message),
                x.at ? null : " ",
                x.at ? null : preact.h("small", null, "(no position)")));
        }
        if (list.length > MSG_ROWS)
            out.push(preact.h("div", { key: "m:" + code, class: "notes" }, `… ${list.length - MSG_ROWS} more`));
    }
    return preact.h(preact.Fragment, null, out);
}
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
function SevLine({ counts }) {
    return preact.h(preact.Fragment, null,
        preact.h("span", { class: "sev err" }, plural(counts.error, "error", "errors")),
        preact.h("span", { class: "sev warn" }, plural(counts.warning, "warning", "warnings")),
        preact.h("span", { class: "sev info" }, `${counts.info} info`));
}
function buildMessages() {
    const box = $("msgList"), C = S && S.check, n = C ? C.counts : null;
    showSection("messages", !!C, C ? C.findings.length : undefined, "Messages", n && n.error ? "err" : n && n.warning ? "warn" : "");
    preact.render(n ? preact.h(SevLine, { counts: n }) : null, $("msgTitle"));
    st.msgOpen = st.msgOpen || new Set();
    preact.render(C ? preact.h(MessagesPanel, { check: C }) : null, box);
}
// ---- panels/project-review.ts
// ================================================================== project review: recorded evidence and a guided finding list (c0239)
const REVIEW = { doc: null, selected: -1, items: [], matches: [] };
const REVIEW_STATE = { "not-run": "Not run", passed: "Passed", failed: "Failed", limited: "Limited" };
function setProjectReview(open) {
    $("projectReview").hidden = !open;
    $("bProjectReview").setAttribute("aria-expanded", String(open));
    if (open) {
        setSidebar(false);
        buildProjectReview();
        $("reviewClose").focus();
    }
    else
        (matchMedia("(max-width:760px)").matches ? $("bSidebar") : $("bProjectReview")).focus();
}
$("bProjectReview").onclick = () => setProjectReview($("projectReview").hidden);
$("reviewClose").onclick = () => setProjectReview(false);
$("reviewJump").onclick = () => { $("reviewFindingHeading").scrollIntoView({ block: "start" }); $("reviewFindingHeading").focus(); };
$("projectReview").addEventListener("keydown", e => {
    if (e.key === "Escape" && !e.isComposing) {
        e.preventDefault();
        e.stopPropagation();
        setProjectReview(false);
    }
});
// The entry of the side bar's head (c0300, design decision 5): "Project review" and the states of its cards.
function reviewCardsOf(ready, data) {
    return data?.cards || [{ id: "read", title: "Read document", state: ready ? "passed" : "not-run" },
        ...["Netlist connectivity", "Electrical rules (ERC)", "Board rules (DRC)", "Copper clearance", "Placement rules", "Zone fill", "Conversion", "Fabrication export"].map(title => ({ title, state: "not-run" }))];
}
function reviewEntry() {
    const ready = !!(S && DOC && REVIEW.doc === DOC.id), cards = reviewCardsOf(ready, ready && S.project_review), n = {};
    for (const c of cards) {
        const k = REVIEW_STATE[c.state] ? c.state : "limited";
        n[k] = (n[k] || 0) + 1;
    }
    const parts = ["failed", "limited", "passed", "not-run"].filter(k => n[k]).map(k => preact.h("span", { class: `rs ${k}` }, `${n[k]} ${REVIEW_STATE[k].toLowerCase()}`));
    preact.render(preact.h(preact.Fragment, null, preact.h("span", { class: "reIc" }, preact.h(Icon, { name: "review" })), preact.h("span", { class: "reText" }, preact.h("b", null, "Project review"), preact.h("small", null, ...parts.flatMap((p, i) => i ? [" · ", p] : [p]))), preact.h("span", { class: "reGo" }, preact.h(Icon, { name: "chevRight", size: 12 }))), $("bProjectReview"));
}
function buildProjectReview() {
    reviewEntry();
    if ($("projectReview").hidden)
        return;
    const ready = S && DOC && REVIEW.doc === DOC.id;
    const data = ready && S.project_review;
    const box = $("reviewCards");
    box.innerHTML = "";
    $("reviewScope").textContent = ready
        ? `${DOC.name}. ${data?.note || "No validation report was supplied. Reading a drawing is not an electrical check."}`
        : "This document has not been read. Select a viewable document to review it.";
    if (data?.binding && !data.binding.matched)
        $("reviewScope").textContent += " " + data.binding.note;
    const stale = ready && RUNS.stale.get(DOC.id);
    if (stale) { // c0303 fix: a write after the checks
        const banner = document.createElement("div");
        banner.className = "staleNote";
        banner.setAttribute("role", "status");
        const p = document.createElement("p");
        p.textContent = stale.text;
        banner.appendChild(p);
        const again = runAgainAction(DOC.id);
        if (again) {
            const b = document.createElement("button");
            b.id = "reviewRunAgain";
            b.textContent = again.label;
            b.disabled = !!RUNS.job;
            b.onclick = again.run;
            banner.appendChild(b);
        }
        box.appendChild(banner);
    }
    for (const card of reviewCardsOf(ready, data)) {
        const details = document.createElement("details"), state = REVIEW_STATE[card.state] ? card.state : "limited";
        details.dataset.card = card.id || card.title;
        details.innerHTML = `<summary><span>${esc(card.title)}</span><span class="reviewState ${state}">${REVIEW_STATE[state]}</span></summary>`;
        const add = text => { const p = document.createElement("p"); p.textContent = text; details.appendChild(p); };
        if (card.evidence)
            add(`Evidence: ${card.evidence}`);
        for (const reason of card.reasons || [])
            add(reason);
        if (card.binding)
            add(card.binding.note);
        if ((card.missing || []).length)
            add(`Not run: ${card.missing.join(", ")}`);
        if (state === "not-run")
            add(RUNS.enabled && CARD_STAGES[card.id] ? "Not run yet: Run checks it now, on this server." : "No result supplied. Run fenolite check separately and reopen with --check FILE, or attach recorded conversion/export results with --report FILE.");
        for (const stage of card.stages || []) {
            add(`${stage.name}: ${stage.status || "unknown"} · ${stage.evidence}`);
            for (const reason of stage.reasons || [])
                add(reason);
            if (stage.limits && Object.keys(stage.limits).length)
                add(`Report limits: ${JSON.stringify(stage.limits)}`);
        }
        runCardControl(details, card);
        box.appendChild(details);
    }
    buildRunPanel();
    buildActionPanel(true);
    REVIEW.items = ready ? [...(S.check?.findings || []).map((item, i) => ({ ...item, checkIndex: i })), ...(S.run_findings || []).map((item, i) => ({ ...item, runIndex: i })), ...(data?.operation_findings || [])] : [];
    const stage = $("reviewStage"), chosen = stage.value;
    stage.innerHTML = '<option value="">All stages</option>';
    for (const name of [...new Set(REVIEW.items.map(x => x.stage || "unassigned"))].sort()) {
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        stage.appendChild(option);
    }
    stage.value = [...stage.options].some(o => o.value === chosen) ? chosen : "";
    REVIEW.selected = -1;
    filterReviewFindings();
}
function filterReviewFindings() {
    const severity = $("reviewSeverity").value, stage = $("reviewStage").value, q = $("reviewSearch").value.trim().toLowerCase();
    REVIEW.matches = REVIEW.items.map((x, i) => i).filter(i => {
        const x = REVIEW.items[i];
        return (!severity || x.severity === severity) && (!stage || (x.stage || "unassigned") === stage) &&
            (!q || [x.code, x.message, x.where, x.hint].some(v => String(v || "").toLowerCase().includes(q)));
    });
    if (!REVIEW.matches.includes(REVIEW.selected))
        REVIEW.selected = REVIEW.matches[0] ?? -1;
    const box = $("reviewFindings");
    box.innerHTML = "";
    $("reviewCount").textContent = REVIEW.items.length ? `${REVIEW.matches.length} of ${REVIEW.items.length} reported findings` : "No findings supplied. This does not mean the project passed its checks.";
    if (REVIEW.items.length && !REVIEW.matches.length)
        $("reviewCount").textContent += " — no matches";
    for (const i of REVIEW.matches) {
        const x = REVIEW.items[i], button = document.createElement("button");
        button.type = "button";
        button.textContent = `${x.severity}: ${x.code} — ${x.message}`;
        button.setAttribute("aria-pressed", String(i === REVIEW.selected));
        button.onclick = () => { REVIEW.selected = i; filterReviewFindings(); };
        box.appendChild(button);
    }
    $("reviewPrevious").disabled = $("reviewNext").disabled = !REVIEW.matches.length;
    const detail = $("reviewDetail"), x = REVIEW.items[REVIEW.selected];
    detail.innerHTML = "";
    if (!x)
        return;
    const h = document.createElement("h3");
    h.textContent = `${x.code} · ${x.severity}`;
    detail.appendChild(h);
    for (const text of [x.message, `Stage: ${x.stage || "unassigned"} · evidence: ${x.evidence || "UNKNOWN"}`, x.where && `Where: ${x.where}`, x.hint && `Guidance: ${x.hint}`,
        x.at ? "Locate highlights the recorded geometry; review does not mark the problem fixed." : "No position on this document. Use the location and original guidance above."]) {
        if (!text)
            continue;
        const p = document.createElement("p");
        p.textContent = text;
        detail.appendChild(p);
    }
    if (x.checkIndex != null && x.at) {
        const button = document.createElement("button");
        button.textContent = "Locate in drawing";
        button.onclick = () => { st.checks = true; setProjectReview(false); selectFinding(x.checkIndex); };
        detail.appendChild(button);
    }
    runLocateButton(x, detail);
    actWaiveButton(x, detail);
}
for (const id of ["reviewSeverity", "reviewStage"])
    $(id).onchange = filterReviewFindings;
$("reviewSearch").oninput = filterReviewFindings;
function stepReviewFinding(direction) {
    if (!REVIEW.matches.length)
        return;
    const k = REVIEW.matches.indexOf(REVIEW.selected);
    REVIEW.selected = REVIEW.matches[(k + direction + REVIEW.matches.length) % REVIEW.matches.length];
    filterReviewFindings();
}
$("reviewPrevious").onclick = () => stepReviewFinding(-1);
$("reviewNext").onclick = () => stepReviewFinding(1);
// ---- Run controls (c0302): a Run button on each card whose stages this server can run, the panel "Run from
// this page", and Locate for the findings of a ready or equivalent run. The client is review/runs.
function runCardControl(details, card) {
    if (!RUNS.enabled || !DOC)
        return;
    const offered = runStages(), stages = (CARD_STAGES[card.id] || []).filter(s => offered.includes(s));
    if (!stages.length)
        return;
    const b = document.createElement("button");
    b.className = "runCard";
    b.textContent = "Run";
    b.dataset.runCard = card.id;
    b.title = `Run ${stages.join(", ")} now (fenolite check; nothing is written)`;
    b.disabled = !!RUNS.job;
    b.setAttribute("aria-label", `Run ${card.title}`);
    b.onclick = e => { e.preventDefault(); e.stopPropagation(); startRun("check", { stages }); };
    details.querySelector("summary").insertBefore(b, details.querySelector(".reviewState"));
}
function runBox(title, body) { const s = document.createElement("div"); s.className = "runBox"; s.innerHTML = `<h4>${esc(title)}</h4>`; body(s); return s; }
function runChecks(name, values, chosen) {
    const g = document.createElement("div");
    g.className = "runGrid";
    for (const v of values) {
        const l = document.createElement("label");
        l.innerHTML = `<input type="checkbox" name="${esc(name)}" value="${esc(v)}" ${chosen.includes(v) ? "checked" : ""}> ${esc(v)}`;
        g.appendChild(l);
    }
    return g;
}
function picked(box, name) { return [...box.querySelectorAll(`input[name="${name}"]:checked`)].map((i) => i.value); }
function buildRunPanel() {
    const panel = $("runPanel");
    if (!panel)
        return;
    panel.innerHTML = "";
    panel.hidden = !RUNS.enabled || !DOC || !(DOC.viewable || DOC.kind === "project");
    if (panel.hidden)
        return;
    const busy = !!RUNS.job, cmds = RUNS.offer.commands || {};
    const head = document.createElement("h3");
    head.textContent = "Run from this page";
    panel.appendChild(head);
    const note = document.createElement("p");
    note.className = "notes";
    note.textContent = "Read-only commands run on this server in the project folder; nothing is written. Results replace the stages they ran and stay bound to the file's revision.";
    panel.appendChild(note);
    const stages = runStages(), defaults = runAltium() ? stages : (cmds.check?.options?.stages?.default || []);
    panel.appendChild(runBox("Checks", s => {
        s.appendChild(runChecks("stage", stages, defaults));
        const row = document.createElement("div");
        row.className = "runRow";
        row.innerHTML = '<button id="runChecks">Run checks</button><button id="runAll">Run all checks</button>';
        s.appendChild(row);
        row.querySelector("#runChecks").onclick = () => { const chosen = picked(s, "stage"); if (chosen.length)
            startRun("check", { stages: chosen });
        else
            runSay("failed", "Choose at least one stage."); };
        row.querySelector("#runAll").onclick = () => startRun("check", {});
    }));
    if (cmds.analyze && DOC.kind === "pcb")
        panel.appendChild(runBox("Analyze", s => {
            const o = cmds.analyze.options.kinds;
            s.appendChild(runChecks("kind", o.choices, o.default));
            const b = document.createElement("button");
            b.id = "runAnalyze";
            b.textContent = "Analyze";
            s.appendChild(b);
            b.onclick = () => { const chosen = picked(s, "kind"); startRun("analyze", chosen.length ? { kinds: chosen } : {}); };
        }));
    if (cmds.ready && !runAltium())
        panel.appendChild(runBox("Readiness", s => {
            s.innerHTML += '<label class="runOpt"><input type="checkbox" id="runNoKicad"> without kicad-cli (ERC and DRC skipped)</label>';
            const b = document.createElement("button");
            b.id = "runReady";
            b.textContent = "Check readiness";
            s.appendChild(b);
            b.onclick = () => startRun("ready", s.querySelector("#runNoKicad").checked ? { no_kicad: true } : {});
        }));
    const others = (PROJECT ? PROJECT.groups.flatMap(g => g.documents) : []).filter(d => d.present && d.viewable && d.id !== DOC.id && d.kind === DOC.kind);
    if (cmds.equivalent && others.length)
        panel.appendChild(runBox("Compare with", s => {
            const sel = document.createElement("select");
            sel.id = "runOther";
            sel.setAttribute("aria-label", "Document to compare with");
            for (const d of others) {
                const o = document.createElement("option");
                o.value = d.id;
                o.textContent = d.name;
                sel.appendChild(o);
            }
            const b = document.createElement("button");
            b.id = "runEquivalent";
            b.textContent = "Compare";
            s.append(sel, b);
            b.onclick = () => startRun("equivalent", { b: sel.value });
        }));
    for (const b of panel.querySelectorAll("button"))
        b.disabled = busy;
}
function runLocateButton(x, detail) {
    if (x.runIndex == null || !x.at)
        return;
    const button = document.createElement("button");
    button.textContent = "Locate in drawing";
    button.onclick = () => {
        setProjectReview(false);
        const b = x.box || [x.at[0], x.at[1], x.at[0], x.at[1]], m = Math.max(b[2] - b[0], b[3] - b[1], 6) * 0.8;
        fit([b[0] - m, b[1] - m, b[2] + m, b[3] + m]);
        inspect(() => imodel("finding", x.code, [findingSection(x, null)], { subtitle: [x.severity, x.stage].filter(Boolean).join(" · "), target: { comp: -1, net: -1 } }));
    };
    detail.appendChild(button);
}
// ---- review/runs.ts
// ================================================================== run checks from the page (c0302)
// Only a live server with a runner offers runs (GET /runs); an exported page never asks. One job at a time:
// the strip shows its command, last progress record, elapsed time and Cancel; the results land on the scene of
// the job's document, and are drawn only while that document is the one shown (the navigation guard).
// The client and the run state live here; the strip is panels/run-strip, the Run controls panels/project-review.
const RUNS = { enabled: false, offer: null, reason: "", job: null, timer: 0, results: new Map(), message: null,
    last: new Map(), stale: new Map() }; // c0303 fix: the last run of each document, and the documents whose results a write made stale
const CARD_STAGES = { connectivity: ["parity", "netlist.assignment_compare"], erc: ["erc.kicad"], drc: ["drc.kicad"],
    clearance: ["copper.clearance"], placement: ["placement.rules"], fill: ["zone.fill"], model: ["model.validate"] };
const RUN_HEADERS = { "Content-Type": "application/json", "X-Fenolite-Run": "1" };
async function runCall(path, body, headers) {
    const r = await fetch(path, body === undefined ? { cache: "no-store" } : { method: "POST", headers: headers || RUN_HEADERS, body: JSON.stringify(body) });
    let data = {};
    try {
        data = await r.json();
    }
    catch (e) {
        data = {};
    }
    return { ok: r.ok, status: r.status, data };
}
function runAltium() { const name = (DOC && DOC.name || "").toLowerCase(); return PROJECT?.source === "altium" || /\.(pcbdoc|schdoc|prjpcb)$/.test(name); }
function runStages() {
    const o = RUNS.offer?.commands?.check?.options?.stages;
    if (!o)
        return [];
    return runAltium() ? o.altium || [] : o.choices || [];
}
async function runsInit() {
    if (!LIVE || PREVIEW_MODE)
        return;
    try {
        const r = await runCall("runs");
        if (!r.ok)
            return;
        RUNS.enabled = !!r.data.enabled;
        RUNS.offer = r.data;
        RUNS.reason = r.data.reason || "";
        if (r.data.busy) {
            RUNS.job = r.data.busy;
            pollRun();
        }
    }
    catch (e) {
        RUNS.enabled = false;
    }
    buildProjectReview();
    runStrip();
}
async function startRun(command, options) {
    if (!RUNS.enabled || RUNS.job || !DOC)
        return;
    RUNS.message = null;
    RUNS.last.set(DOC.id, { command, options });
    const r = await runCall("run", { command, doc: DOC.id, options });
    if (r.status === 409 && r.data.job) {
        RUNS.job = { job: r.data.job, command, doc: DOC.id, state: "running", progress: [], elapsed: 0 };
        pollRun();
        return;
    }
    if (!r.ok) {
        runSay("failed", r.data.error || `the server answered ${r.status}`);
        return;
    }
    RUNS.job = { job: r.data.job, command, doc: DOC.id, state: "running", progress: [], elapsed: 0 };
    runRefresh();
    pollRun();
}
function runRefresh() { buildProjectReview(); runStrip(); if (S && !S.kind)
    buildRoles(); }
function runCancel() {
    const j = RUNS.job;
    if (!j)
        return null;
    j.cancelling = true;
    runStrip();
    return runCall(`run/${encodeURIComponent(j.job)}/cancel`, {});
}
function pollRun() {
    clearTimeout(RUNS.timer);
    RUNS.timer = setTimeout(async () => {
        const mine = RUNS.job;
        if (!mine)
            return;
        let r;
        try {
            r = await runCall(`run/${encodeURIComponent(mine.job)}`);
        }
        catch (e) {
            r = { ok: false, status: 0, data: {} };
        }
        if (RUNS.job !== mine)
            return;
        if (!r.ok) {
            RUNS.job = null;
            runSay("failed", "The server no longer knows this run.");
            runRefresh();
            return;
        }
        if (r.data.state === "running") {
            RUNS.job = { ...mine, ...r.data };
            runStrip();
            pollRun();
            return;
        }
        RUNS.job = null;
        runFinished(r.data);
        runRefresh();
    }, 500);
}
function runFinished(job) {
    if (job.state === "cancelled")
        return runSay("cancelled", `${job.command} was cancelled; nothing changed.`);
    if (job.state === "timeout")
        return runSay("cancelled", `${job.command} ran past the time limit and was stopped; nothing changed.`);
    if (job.state !== "done") {
        const e = job.error || {}, missing = job.exit === 6 ? " The stages that need kicad-cli could not run." : "";
        return runSay("failed", `${job.command} failed${e.code ? ` (${e.code})` : ""}: ${e.message || "no reason given"}${missing}`, e.hint);
    }
    RUNS.results.set(job.doc, { ...(RUNS.results.get(job.doc) || {}), [job.command]: job });
    if (job.command === "check")
        RUNS.stale.delete(job.doc); // fresh results for the current files
    const sc = SCENES.get(job.doc);
    if (sc)
        runApply(sc, job);
    const n = (job.envelope?.issues || []).length;
    runSay("done", `${job.command} finished: exit ${job.exit}, ${n} finding${n === 1 ? "" : "s"}.` + (job.note ? ` ${job.note}` : "") + (DOC && DOC.id !== job.doc ? " Results kept for their document." : ""));
}
function runPoints(list) { const f = v => v * MM; for (const x of list) {
    if (x.at)
        x.at = x.at.map(f);
    if (x.box)
        x.box = x.box.map(f);
} return list; }
function runApply(sc, job) {
    const copy = v => JSON.parse(JSON.stringify(v));
    if (job.check) {
        sc.check = copy(job.check);
        checkToMM(sc);
    }
    if (job.review)
        sc.project_review = copy(job.review);
    if (job.overlays && sc.kind == null) {
        const items = copy(job.overlays);
        for (const o of items) {
            o.pts = o.pts.map(p => p.map(v => v * MM));
            if (o.bbox)
                o.bbox = o.bbox.map(v => v * MM);
        }
        sc.overlays = (sc.overlays || []).filter(o => o.source !== "run:analyze").concat(items);
        const ids = new Set((job.groups || []).map(g => g.id));
        sc.meta.findings = (sc.meta.findings || []).filter(g => !ids.has(g.id)).concat(copy(job.groups || []));
    }
    if (job.findings)
        sc.run_findings = runPoints(copy(job.findings));
    if (job.command === "roles" && sc.kind == null) {
        sc.roles = job.roles ? copy(job.roles) : null;
        rolesToMM(sc);
    } // c0305
    if (S === sc && DOC && DOC.id === job.doc) {
        if (sc.kind == null) {
            buildFindings();
            if (job.command === "roles") {
                resetRoleCache();
                buildRoles();
                buildLayers();
                refreshInspector();
            }
        }
        buildMessages();
        buildProjectReview();
        draw();
    }
}
function runReapply(scene) {
    const kept = DOC && RUNS.results.get(DOC.id);
    if (!kept || scene.runApplied)
        return;
    scene.runApplied = true;
    for (const command of ["analyze", "ready", "equivalent"])
        if (kept[command])
            runApply(scene, kept[command]);
}
function runSay(kind, text, hint, action) { RUNS.message = { kind, text, hint, action }; runStrip(); }
// c0303, fix of 2026-10-29: a write of an action can change what the last checks judged (a waiver writes the
// project file, not the board, so the board's digest still matches). The results of that document are marked
// stale until a check runs again; the strip, the Project review and the inspector offer Run again.
function markStale(doc, text) { RUNS.stale.set(doc, { text, at: new Date().toLocaleTimeString() }); runSay("stale", text, undefined, runAgainAction(doc)); runRefresh(); refreshInspector(); }
function runAgainAction(doc) { return RUNS.enabled ? { label: "Run again", run: () => runAgain(doc) } : null; }
function runAgain(doc) {
    const id = doc || (DOC && DOC.id);
    if (!id || !DOC || DOC.id !== id)
        return;
    const last = RUNS.last.get(id) || { command: "check", options: {} };
    startRun(last.command, last.options);
}
window.FenoliteRuns = { start: startRun, cancel: runCancel, state: RUNS }; // for the toolbar and palette commands (c0300)
// ---- panels/run-strip.tsx
// The run strip of c0302, a Preact component (change c0304, decision 10): under the toolbar, the running job's
// command, its last progress record, the elapsed time and Cancel; after it, the outcome with Dismiss. The
// strip's class names its state (running, done, failed, cancelled).
function RunStrip({ job, message }) {
    if (job) {
        const last = (job.progress || []).slice(-1)[0], step = last ? [last.step, last.detail].filter(Boolean).join(" · ") : "starting";
        return preact.h(preact.Fragment, null,
            preact.h("span", { class: "runSpin", "aria-hidden": "true" }),
            preact.h("b", null, job.command),
            preact.h("span", null, step),
            preact.h("span", null, `${Number(job.elapsed || 0).toFixed(0)} s`),
            preact.h("button", { id: "runCancel", disabled: !!job.cancelling, onClick: () => runCancel() }, "Cancel"));
    }
    if (!message)
        return null;
    return preact.h(preact.Fragment, null,
        preact.h("span", null, message.text),
        message.hint ? preact.h("small", null, message.hint) : null,
        message.action ? preact.h("button", { id: "runAgain", class: "primary", onClick: () => { const a = message.action; RUNS.message = null; runStrip(); a.run(); } }, message.action.label) : null,
        preact.h("button", { onClick: () => { RUNS.message = null; runStrip(); } }, "Dismiss"));
}
function runStrip() {
    const el = $("runStrip");
    if (!el)
        return;
    const j = RUNS.job, m = RUNS.message;
    el.hidden = !j && !m;
    el.className = j ? "running" : m ? m.kind : "";
    preact.render(preact.h(RunStrip, { key: j ? "job" : "message", job: j, message: m }), el);
    refreshToolbar(); // c0300: Run checks follows the job
}
// ---- actions/actions.ts
// ================================================================== writing actions (c0303)
// Only a page served with --allow-actions offers them (GET /actions). Every action is a dry run first: the
// plan dialog names the files, the issues and the evidence, and draws the staged board's changes over the
// current one. Confirm writes exactly that plan (--confirm --plan); the receipt follows, then the document is
// read again. Undo plans `restore` on a receipt of this session, reviewed and confirmed the same way.
// The client, the action forms of the Project review and Waive live here; the dialog is dialogs/plan-review,
// the list of this session's writes panels/receipts.
const ACTS = { failed: false, enabled: false, token: "", offer: null, doc: null, reason: "", receipts: [], job: null, timer: 0, request: null, saved: null, open: null };
const ACT_FORMS = ["fill", "tidy", "silk", "testpoints", "export", "bom"];
function actHeaders() { return { "Content-Type": "application/json", "X-Fenolite-Action": "1", "X-Fenolite-Token": ACTS.token }; }
async function actionsLoad() {
    if (!LIVE || PREVIEW_MODE || !DOC)
        return;
    const doc = DOC.id;
    ACTS.failed = false;
    try {
        const r = await fetch(`actions?doc=${encodeURIComponent(doc)}`, { cache: "no-store", headers: { "X-Fenolite-Action": "1" } });
        const data = await r.json();
        if (!DOC || DOC.id !== doc)
            return;
        ACTS.enabled = !!data.enabled;
        ACTS.token = data.token || "";
        ACTS.offer = data.actions || {};
        ACTS.receipts = data.receipts || [];
        ACTS.reason = data.reason || "";
        ACTS.doc = doc;
    }
    catch (e) {
        ACTS.enabled = false;
        ACTS.doc = doc;
        ACTS.failed = true;
    } // c0301: the Project review asks again when it opens
    buildActionPanel();
    refreshInspector(); // c0301: the inspector offers the actions that apply
}
function actLen(mm) { return UNIT === "mil" ? `${(mm / MIL_MM).toFixed(2)}mil` : `${mm.toFixed(3)}mm`; }
function actField(key, o, value) {
    const id = `act_${key}`, label = esc(o.label || key);
    if (o.type === "boolean")
        return `<label class="runOpt"><input type="checkbox" data-opt="${key}" ${(value ?? o.default) ? "checked" : ""}> ${label}</label>`;
    if (o.type === "choice")
        return `<label class="actField">${label}<select data-opt="${key}"><option value="">default</option>${o.choices.map(c => `<option ${c === value ? "selected" : ""}>${esc(c)}</option>`).join("")}</select></label>`;
    if (o.type === "kinds")
        return `<div class="runGrid">${o.choices.map(c => `<label><input type="checkbox" data-kind="${key}" value="${esc(c)}" ${(o.default || []).includes(c) ? "checked" : ""}> ${esc(c)}</label>`).join("")}</div>`;
    const hint = o.type === "length" ? (UNIT === "mil" ? "e.g. 100mil" : "e.g. 2.54mm") : o.type === "angle" ? "degrees" : "";
    return `<label class="actField">${label}<input id="${id}" data-opt="${key}" value="${esc(value ?? (typeof o.default === "string" ? o.default : ""))}" placeholder="${hint}" ${o.required ? "required" : ""}></label>`;
}
function actOptions(box) {
    const out = {};
    for (const el of box.querySelectorAll("[data-opt]")) {
        const k = el.dataset.opt;
        if (el.type === "checkbox")
            out[k] = el.checked;
        else if (el.value.trim() !== "")
            out[k] = k === "refs" ? el.value.split(",").map(s => s.trim()).filter(Boolean) : el.value.trim();
    }
    const kinds = {};
    for (const el of box.querySelectorAll("[data-kind]:checked"))
        (kinds[el.dataset.kind] = kinds[el.dataset.kind] || []).push(el.value);
    return { ...out, ...kinds };
}
function actForm(name, values) {
    const a = ACTS.offer[name], d = document.createElement("details");
    d.className = "actBox";
    d.dataset.action = name;
    const fields = Object.entries(a.options).map(([k, o]) => actField(k, o, values && values[k])).join("");
    d.innerHTML = `<summary>${esc(a.title)}</summary>${a.note ? `<p class="notes">${esc(a.note)}</p>` : ""}${fields}<div class="runRow"><button class="actPlan">Review plan…</button></div>`;
    const plan = d.querySelector(".actPlan");
    plan.onclick = () => actPlan(name, actOptions(d));
    if (!a.available) {
        plan.disabled = true;
        d.title = a.why || "";
    }
    if (name === "move")
        actNudge(d);
    return d;
}
function actNudge(box) {
    box.addEventListener("keydown", e => {
        const map = { ArrowLeft: ["x", -1], ArrowRight: ["x", 1], ArrowUp: ["y", -1], ArrowDown: ["y", 1] }, m = map[e.key];
        if (!m || !(e.target instanceof HTMLInputElement) || !["x", "y"].includes(e.target.dataset.opt))
            return;
        const f = box.querySelector(`[data-opt="${m[0]}"]`), v = /^(-?\d+(?:\.\d+)?)(mm|mil|um)$/.exec(f.value.trim());
        if (!v)
            return;
        e.preventDefault();
        const step = v[2] === "mil" ? 1 : v[2] === "um" ? 100 : 0.1;
        f.value = `${(+v[1] + m[1] * step * (e.shiftKey ? 10 : 1)).toFixed(v[2] === "mm" ? 3 : 1)}${v[2]}`;
    });
}
function buildActionPanel(retry = false) {
    const panel = $("actionPanel");
    if (!panel)
        return;
    if (LIVE && DOC && (ACTS.doc !== DOC.id || (retry && ACTS.failed))) {
        ACTS.doc = DOC.id;
        actionsLoad();
    }
    panel.innerHTML = "";
    panel.hidden = !ACTS.enabled || !DOC || ACTS.doc !== DOC.id;
    if (panel.hidden)
        return;
    const head = document.createElement("h3");
    head.textContent = "Actions (writes files)";
    panel.appendChild(head);
    const unavailable = Object.values(ACTS.offer).find((a) => !a.available);
    const note = document.createElement("p");
    note.className = "notes";
    note.textContent = unavailable ? unavailable.why : "Each action shows its plan on the board first; nothing is written until you confirm. Every write keeps a backup and can be undone.";
    panel.appendChild(note);
    if (unavailable)
        return;
    for (const name of ACT_FORMS)
        if (ACTS.offer[name])
            panel.appendChild(actForm(name));
    const sel = st.selComp >= 0 && S && S.comps ? S.comps[st.selComp] : null;
    if (ACTS.offer.move && S && S.comps)
        panel.appendChild(actForm("move", sel ? { ref: sel.ref, x: actLen(sel.x), y: actLen(sel.y), rot: String(sel.rotation ?? "") } : {}));
    if (ACTS.offer.shift)
        panel.appendChild(actForm("shift", { refs: sel ? sel.ref : "", dx: actLen(1), dy: actLen(0) }));
    if (ACTS.offer.turn)
        panel.appendChild(actForm("turn", sel ? { refs: sel.ref, about_x: actLen(sel.x), about_y: actLen(sel.y), angle: "90" } : {}));
    buildReceipts(panel, ACTS.receipts);
    for (const b of panel.querySelectorAll("button"))
        if (ACTS.job)
            b.disabled = true;
}
function waiveBlocked() {
    const b = S && S.project_review?.binding, stale = DOC && RUNS.stale.get(DOC.id);
    if (stale)
        return stale.text;
    if (b && (!b.matched || (b.sha256 && S.meta?.sha256 && b.sha256 !== S.meta.sha256)))
        return "This finding comes from a check of an earlier revision of the file, so its index may name another violation now. Run the checks again before waiving it.";
    return "";
}
function actWaiveButton(x, detail) {
    if (!ACTS.enabled || x.checkIndex == null || x.stage !== "drc.kicad" || !ACTS.offer?.waive?.available)
        return;
    const why = waiveBlocked();
    if (why) {
        const p = document.createElement("p");
        p.className = "actWhy";
        p.id = "actWaiveWhy";
        p.textContent = `Waive is not offered. ${why}`;
        detail.appendChild(p);
        return;
    }
    const box = document.createElement("div");
    box.className = "actWaive";
    box.innerHTML = '<label class="actField">Reason for the waiver (stored in the project)<input id="actReason" maxlength="300" placeholder="Accepted by design: …"></label><button id="actWaive">Waive finding…</button>';
    const reasonField = box.querySelector("#actReason");
    box.querySelector("#actWaive").onclick = () => {
        const reason = reasonField.value.trim();
        if (!reason) {
            reasonField.focus();
            return;
        }
        actPlan("waive", { finding: x.checkIndex, reason });
    };
    detail.appendChild(box);
}
async function actPost(path, body) {
    const r = await fetch(path, { method: "POST", headers: actHeaders(), body: JSON.stringify(body) });
    let data = {};
    try {
        data = await r.json();
    }
    catch (e) {
        data = {};
    }
    return { ok: r.ok, status: r.status, data };
}
async function actPlan(action, options) {
    if (!ACTS.enabled || ACTS.job || !DOC)
        return;
    ACTS.request = { action, options, doc: DOC.id };
    actDialog({ phase: "planning", title: ACTS.offer[action]?.title || action });
    const r = await actPost("action/plan", { action, doc: DOC.id, options });
    if (!r.ok)
        return actDialog({ phase: "error", title: ACTS.offer[action]?.title || action, message: r.data.error || `the server answered ${r.status}` });
    actFollow(r.data.job, "plan");
}
async function actUndo(receipt) {
    if (!ACTS.enabled || ACTS.job)
        return;
    ACTS.request = { undo: receipt };
    actDialog({ phase: "planning", title: "Undo a write" });
    const r = await actPost("action/undo", { receipt });
    if (!r.ok)
        return actDialog({ phase: "error", title: "Undo a write", message: r.data.error || `the server answered ${r.status}` });
    actFollow(r.data.job, "plan");
}
async function actConfirm(job) {
    actDialog({ phase: "planning", title: ACTS.open?.title || "Action", status: "Writing the reviewed plan…" });
    const r = await actPost("action/confirm", { job });
    if (!r.ok) {
        actPreviewOff();
        return actDialog({ phase: "error", title: "Action", message: r.data.error || `the server answered ${r.status}` });
    }
    actFollow(r.data.job, "confirm");
}
function actAgain() { const q = ACTS.request; if (!q)
    return actClose(); if (q.undo)
    actUndo(q.undo);
else
    actPlan(q.action, q.options); }
async function actCancel() {
    const j = ACTS.job;
    actClose();
    if (j)
        await runCall(`run/${encodeURIComponent(j.job)}/cancel`, {});
}
function actFollow(job, phase) {
    ACTS.job = { job, phase };
    buildActionPanel();
    clearTimeout(ACTS.timer);
    const step = async () => {
        const mine = ACTS.job;
        if (!mine)
            return;
        let r;
        try {
            r = await runCall(`run/${encodeURIComponent(mine.job)}`);
        }
        catch (e) {
            r = { ok: false, data: {} };
        }
        if (ACTS.job !== mine)
            return;
        if (r.ok && r.data.state === "running") {
            actProgress(r.data);
            ACTS.timer = setTimeout(step, 400);
            return;
        }
        ACTS.job = null;
        buildActionPanel();
        if (!ACTS.open)
            return; // the dialog was closed: a cancelled job says nothing more
        if (!r.ok)
            return actDialog({ phase: "error", title: "Action", message: "The server no longer knows this job." });
        if (mine.phase === "plan")
            actPlanned(r.data);
        else
            actWritten(r.data);
    };
    ACTS.timer = setTimeout(step, 300);
}
function actProgress(job) {
    if (!ACTS.open || ACTS.open.phase !== "planning")
        return;
    const last = (job.progress || []).slice(-1)[0];
    ACTS.open = { ...ACTS.open, status: `${job.command} running · ${last ? [last.step, last.detail].filter(Boolean).join(" · ") : "starting"} · ${Number(job.elapsed || 0).toFixed(0)} s` };
    actRender(ACTS.open);
}
function actPreview(diff) {
    if (!S || S.kind != null)
        return;
    if (ACTS.saved === null)
        ACTS.saved = { diff: S.diff || null, on: st.diff };
    if (diff) {
        const holder = { diff: JSON.parse(JSON.stringify(diff)) };
        diffToMM(holder);
        S.diff = holder.diff;
        S.diff.old = { name: "the plan (staged bytes)" };
        st.diff = true;
    }
    else
        S.diff = ACTS.saved.diff;
    buildDiffList();
    draw();
}
function actPreviewOff() { if (ACTS.saved && S) {
    S.diff = ACTS.saved.diff;
    st.diff = ACTS.saved.on;
    buildDiffList();
    draw();
} ACTS.saved = null; }
function actPlanned(job) {
    const title = job.action === "undo" ? "Undo a write" : ACTS.offer[job.action]?.title || job.action;
    if (job.state !== "done")
        return actDialog({ phase: "error", title, message: actError(job) });
    actPreview(job.preview || null);
    actDialog({ phase: "plan", title, job });
}
function actWritten(job) {
    const title = job.action === "undo" ? "Undo a write" : ACTS.offer[job.action]?.title || job.action;
    actPreviewOff();
    if (job.review_again)
        return actDialog({ phase: "changed", title, message: actError(job), hint: job.hint });
    if (job.state !== "done")
        return actDialog({ phase: "error", title, message: actError(job) });
    actDialog({ phase: "receipt", title, job });
    const written = (job.receipt?.written || []).map(w => String(w.path)), own = DOC && DOC.id === job.doc ? DOC.name.toLowerCase() : "";
    const others = written.filter(p => p.replace(/\\/g, "/").split("/").pop().toLowerCase() !== own);
    if (job.action !== "undo" && others.length && (job.action === "waive" || others.some(p => /\.(kicad_pro|kicad_dru)$/i.test(p))))
        markStale(job.doc, `The checks predate this write: ${others.join(", ")} changed (${title.toLowerCase()}). Their results are stale until the checks run again.`);
    if (DOC && DOC.id === job.doc) {
        invalidateScene(job.doc);
        openDoc(DOC, true);
    }
    actionsLoad();
}
function actError(job) { const e = job.error || {}; return `${job.command} ${job.state}${e.code ? ` (${e.code})` : ""}: ${e.message || "no reason given"}${e.hint ? `. ${e.hint}` : ""}`; }
window.FenoliteActions = { plan: actPlan, undo: actUndo, state: ACTS }; // for the toolbar, palette and inspector (c0300, c0301)
// ---- dialogs/plan-review.tsx
// The plan review of c0303, a Preact dialog (change c0304, decision 10): one modal `#planDialog` whose body and
// buttons follow the phase of the action: planning (the dry run or the write is running), plan (the files, the
// issues, the evidence and Confirm), receipt, changed (FEN-4002: review again) and error.
const PLAN_TITLES = { planning: "Planning", plan: "Review the plan", receipt: "Written", changed: "The file changed", error: "Not planned" };
const actShort = h => h ? `${String(h).slice(0, 12)}…` : "new file";
function PlanIssues({ issues }) {
    if (!issues.length)
        return preact.h("p", { class: "notes" }, "No issue reported.");
    const order = { error: 0, warning: 1, info: 2 };
    return preact.h("ul", { class: "planIssues" }, [...issues].sort((a, b) => (order[a.severity] ?? 3) - (order[b.severity] ?? 3)).map(x => preact.h("li", { class: x.severity }, `${x.severity}: ${x.code} — ${x.message}`)));
}
function PlanFiles({ writes }) {
    return preact.h("table", { class: "planFiles" },
        preact.h("thead", null,
            preact.h("tr", null,
                preact.h("th", null, "Writes"),
                preact.h("th", null, "Kind"),
                preact.h("th", null, "Bytes"),
                preact.h("th", null, "New SHA-256"),
                preact.h("th", null, "Replaces"))),
        preact.h("tbody", null, writes.map(w => preact.h("tr", null,
            preact.h("td", null, String(w.path)),
            preact.h("td", null, w.kind || ""),
            preact.h("td", null, String(w.bytes)),
            preact.h("td", { title: String(w.sha256) }, actShort(w.sha256)),
            preact.h("td", { title: w.replaces || "" }, actShort(w.replaces))))));
}
function PlanPlan({ job }) {
    const plan = job.plan;
    if (!plan)
        return preact.h(preact.Fragment, null,
            preact.h("p", { class: "notes" }, "The command planned no write."),
            preact.h(PlanIssues, { issues: job.envelope?.issues || [] }));
    const q = ACTS.request || {}, note = ACTS.offer?.[job.action]?.note;
    const lead = q.undo ? `Puts back the backups of write ${q.undo}; restore refuses if a written file changed since.`
        : note ? note[0].toUpperCase() + note.slice(1) + (q.options?.reason ? `, with the reason “${q.options.reason}”.` : ".") : null;
    const evidence = plan.evidence ? plan.evidence.level + (plan.evidence.oracle ? ` (${plan.evidence.oracle})` : "") : "UNKNOWN";
    return preact.h(preact.Fragment, null,
        lead ? preact.h("p", null, lead) : null,
        preact.h(PlanFiles, { writes: plan.writes }),
        preact.h(PlanIssues, { issues: plan.issues }),
        preact.h("p", { class: "notes" }, `Evidence: ${evidence}`),
        job.preview ? preact.h("p", { class: "notes" }, `On the board: ${job.preview.changes.length} change(s) — added in green, removed in magenta, moved parts as arrows; listed under Changes.`)
            : job.preview_note ? preact.h("p", { class: "notes" }, job.preview_note) : null,
        plan.refused ? preact.h("p", { class: "planError" }, plan.refused) : null,
        !plan.confirmable && !plan.refused ? preact.h("p", { class: "planError" }, "An error finding plans no write: Confirm is disabled.") : null);
}
function PlanReceipt({ job }) {
    const r = job.receipt || {};
    return preact.h(preact.Fragment, null,
        preact.h("p", null, `Receipt ${r.id || "?"}: the plan was written; the document is read again.`),
        preact.h("table", { class: "planFiles" },
            preact.h("thead", null,
                preact.h("tr", null,
                    preact.h("th", null, "Written"),
                    preact.h("th", null, "SHA-256"))),
            preact.h("tbody", null, (r.written || []).map(w => preact.h("tr", null,
                preact.h("td", null, String(w.path)),
                preact.h("td", { title: String(w.sha256) }, actShort(w.sha256)))))),
        preact.h("p", { class: "notes" }, (r.backup || []).length ? `Backups kept: ${r.backup.join(", ")}` : "No backup was needed (new files only)."));
}
function PlanBody({ view }) {
    if (view.phase === "planning")
        return preact.h("p", { class: "notes", id: "planStatus" }, view.status || "Running the dry run; nothing is written.");
    if (view.phase === "error")
        return preact.h("p", { class: "planError" }, view.message);
    if (view.phase === "changed")
        return preact.h(preact.Fragment, null,
            preact.h("p", { class: "planError" }, view.message),
            preact.h("p", { class: "notes" }, view.hint || "The file changed since the review."));
    if (view.phase === "plan")
        return preact.h(PlanPlan, { job: view.job });
    if (view.phase === "receipt")
        return preact.h(PlanReceipt, { job: view.job });
    return null;
}
function PlanFoot({ view }) {
    if (view.phase === "planning")
        return preact.h("button", { onClick: actCancel }, "Cancel");
    if (view.phase === "error")
        return preact.h("button", { onClick: actClose }, "Close");
    if (view.phase === "changed")
        return preact.h(preact.Fragment, null,
            preact.h("button", { class: "primary", onClick: actAgain }, "Review again"),
            preact.h("button", { onClick: actClose }, "Close"));
    if (view.phase === "plan") {
        const plan = view.job.plan;
        if (!plan)
            return preact.h("button", { onClick: actClose }, "Close");
        return preact.h(preact.Fragment, null,
            preact.h("button", { class: "primary", id: "planConfirm", disabled: !plan.confirmable, onClick: () => actConfirm(view.job.job) }, "Confirm and write"),
            preact.h("button", { onClick: actClose }, "Cancel"));
    }
    if (view.phase === "receipt") {
        const r = view.job.receipt || {};
        return preact.h(preact.Fragment, null,
            r.id && view.job.action !== "undo" ? preact.h("button", { onClick: () => actUndo(r.id) }, "Undo\u2026") : null,
            preact.h("button", { class: "primary", onClick: actClose }, "Close"));
    }
    return null;
}
function actRender(view) {
    $("planTitle").textContent = PLAN_TITLES[view.phase] + ` · ${view.title}`;
    preact.render(preact.h(PlanBody, { key: view.phase, view: view }), $("planBody"));
    preact.render(preact.h(PlanFoot, { key: view.phase, view: view }), $("planFoot"));
}
function actDialog(view) {
    const dlg = $("planDialog");
    ACTS.open = view;
    actRender(view);
    if (!dlg.open)
        dlg.showModal();
    const foot = $("planFoot");
    (foot.querySelector("button.primary:not([disabled])") || foot.querySelector("button")).focus();
}
function actClose() { actPreviewOff(); const dlg = $("planDialog"); if (dlg.open)
    dlg.close(); ACTS.open = null; }
$("planDialog").addEventListener("cancel", e => { e.preventDefault(); actClose(); });
// ---- panels/receipts.tsx
// The writes of this session (c0303), a Preact list at the foot of the Actions panel (change c0304, decision
// 10): one row per receipt with its time, action and files, and Undo, which plans `restore` on it.
function ReceiptList({ receipts }) {
    return preact.h(preact.Fragment, null,
        preact.h("h4", null, "Writes of this session"),
        receipts.map(r => preact.h("div", { class: "actReceipt" },
            preact.h("span", null, `${r.time || ""} · ${r.action} · ${(r.files || []).join(", ")}`),
            preact.h("button", { onClick: () => actUndo(r.id) }, "Undo\u2026"))));
}
function buildReceipts(panel, receipts) {
    if (!receipts.length)
        return;
    const box = document.createElement("div");
    box.className = "actReceipts";
    panel.appendChild(box);
    preact.render(preact.h(ReceiptList, { receipts: receipts }), box);
}
// ---- dialogs/catalog-selection.ts
// ================================================================== catalog selection (c0240)
const CATSEL = { generation: 0, symbols: [], footprints: [], symbol: null, footprint: null, validFilters: true, candidates: [], symbolCandidates: [], loading: false, mapping: new Map() };
async function openCatalogSelection() {
    if (PREVIEW_MODE || !PROJECT || PROJECT.source !== "catalog")
        return;
    const generation = ++CATSEL.generation;
    CATSEL.loading = true;
    $("catalogSelection").showModal();
    $("catMessage").textContent = "Loading the installed definitions…";
    try {
        const docs = allDocs().filter(d => d.viewable && d.present);
        const scenes = await Promise.all(docs.map(async (d) => ({ doc: d.id, scene: await sceneOf(d) })));
        if (generation !== CATSEL.generation || !$("catalogSelection").open)
            return;
        CATSEL.symbols = [];
        CATSEL.footprints = [];
        for (const { doc, scene } of scenes)
            for (const item of scene?.items || []) {
                const facts = item.catalog_selection;
                if (!facts)
                    continue;
                (facts.kind === "symbol" ? CATSEL.symbols : CATSEL.footprints).push({ ...item, doc });
            }
        CATSEL.loading = false;
        filterCatalogSelection();
    }
    catch (e) {
        if (generation === CATSEL.generation) {
            CATSEL.loading = false;
            $("catMessage").textContent = `Could not load catalog: ${e.message}`;
        }
    }
}
$("bCatalogSelection").onclick = openCatalogSelection;
$("catClose").onclick = () => $("catalogSelection").close();
$("catalogSelection").addEventListener("close", () => {
    if ($("catalogSelection").open)
        return;
    CATSEL.generation++;
    CATSEL.loading = false;
    $("catSymbolPreview").replaceChildren();
    $("catFootprintPreview").replaceChildren();
});
function catalogOptions(id, items, selected, placeholder) {
    const select = $(id);
    select.innerHTML = "";
    const option = document.createElement("option");
    option.value = "";
    option.textContent = placeholder;
    select.appendChild(option);
    for (const item of items) {
        const option = document.createElement("option");
        option.value = item.lib_id;
        option.textContent = item.lib_id;
        select.appendChild(option);
    }
    if (selected && !items.some(x => x.lib_id === selected.lib_id)) {
        const option = document.createElement("option");
        option.value = selected.lib_id;
        option.textContent = `${selected.lib_id} (outside filters)`;
        option.disabled = true;
        select.appendChild(option);
    }
    select.value = selected?.lib_id || "";
}
function filterCatalogSelection() {
    if (CATSEL.loading)
        return;
    $("catReviewed").checked = false;
    const match = (item, text) => !text || [item.lib_id, item.category, item.summary].some(x => String(x || "").toLowerCase().includes(text));
    const sq = $("catSymbolQuery").value.trim().toLowerCase(), fq = $("catFootprintQuery").value.trim().toLowerCase();
    const symbols = CATSEL.symbols.filter(x => match(x, sq));
    const nums = {}, errors = [];
    for (const id of ["PadCount", "SpacingMin", "SpacingMax", "WidthMin", "WidthMax", "HeightMin", "HeightMax"]) {
        const input = $("cat" + id), text = input.value.trim(), number = text === "" ? null : Number(text);
        const invalid = input.validity.badInput || number !== null && (!Number.isFinite(number) || number < 0 || id === "PadCount" && !Number.isInteger(number));
        input.setAttribute("aria-invalid", String(invalid));
        if (invalid)
            errors.push("Use nonnegative numbers; pad count must be an integer.");
        nums[id] = number;
    }
    for (const kind of ["Spacing", "Width", "Height"])
        if (nums[kind + "Min"] !== null && nums[kind + "Max"] !== null && nums[kind + "Min"] > nums[kind + "Max"])
            errors.push(`${kind}: minimum exceeds maximum.`);
    const range = (value, kind) => (nums[kind + "Min"] === null || value !== null && value >= nums[kind + "Min"] * 1e6) && (nums[kind + "Max"] === null || value !== null && value <= nums[kind + "Max"] * 1e6);
    const mounting = $("catMounting").value;
    const footprints = errors.length ? [] : CATSEL.footprints.filter(item => {
        const f = item.catalog_selection, pads = f.pads.filter(p => p.number);
        return match(item, fq) && (!mounting || f.mounting === mounting) && (nums.PadCount === null || f.pad_numbers.length === nums.PadCount) && range(f.min_center_spacing_nm, "Spacing") &&
            (!["WidthMin", "WidthMax", "HeightMin", "HeightMax"].some(k => nums[k] !== null) || pads.length > 0) && pads.every(p => range(p.width_nm, "Width") && range(p.height_nm, "Height"));
    });
    CATSEL.validFilters = !errors.length;
    CATSEL.candidates = footprints.map(x => x.lib_id);
    CATSEL.symbolCandidates = symbols.map(x => x.lib_id);
    catalogOptions("catSymbol", symbols, CATSEL.symbol, "Choose a symbol");
    catalogOptions("catFootprint", footprints, CATSEL.footprint, "Choose a footprint");
    $("catMessage").textContent = errors.length ? errors.join(" ") : `${symbols.length} symbols · ${footprints.length} footprints match${!symbols.length || !footprints.length ? " — no matches in one group" : ""}. Select both definitions; compatibility must be checked against your part's datasheet.`;
    catalogSelectionFacts();
}
function catalogSelectionFacts() {
    const s = CATSEL.symbol, f = CATSEL.footprint;
    $("catSymbolFacts").textContent = s ? `${s.lib_id} · ${s.catalog_selection.pins.length} pins · ${s.evidence} · sources: ${s.sources.join(", ")}` : "No symbol selected.";
    if (f) {
        const facts = f.catalog_selection, spacing = facts.min_center_spacing_nm;
        $("catFootprintFacts").textContent = `${f.lib_id} · ${facts.mounting} · ${facts.pad_numbers.length} numbered pads (${facts.pad_count} physical pads) · min centre spacing ${spacing === null ? "unknown" : (spacing / 1e6).toFixed(6) + " mm"} · ${f.evidence} · sources: ${f.sources.join(", ")}`;
    }
    else
        $("catFootprintFacts").textContent = "No footprint selected.";
    catalogPreview("catSymbolPreview", s, "Symbol");
    catalogPreview("catFootprintPreview", f, "Footprint");
    updateCatalogSnippet();
}
function catalogPreview(id, item, kind) {
    const host = $(id);
    if (!item || !$("catalogSelection").open || PREVIEW_MODE) {
        host.replaceChildren();
        return;
    }
    if (host.firstElementChild?.dataset.item === item.lib_id)
        return;
    const url = new URL(location.href);
    url.hash = new URLSearchParams({ doc: item.doc, item: item.lib_id, preview: "1" }).toString();
    const frame = document.createElement("iframe");
    frame.className = "catPreview";
    frame.title = `${kind}: ${item.lib_id}`;
    frame.dataset.item = item.lib_id;
    frame.setAttribute("sandbox", "allow-scripts");
    frame.src = url.href;
    host.replaceChildren(frame);
}
for (const id of ["SymbolQuery", "FootprintQuery", "PadCount", "SpacingMin", "SpacingMax", "WidthMin", "WidthMax", "HeightMin", "HeightMax"])
    $("cat" + id).oninput = filterCatalogSelection;
$("catMounting").onchange = filterCatalogSelection;
$("catSymbol").onchange = () => { CATSEL.symbol = CATSEL.symbols.find(x => x.lib_id === $("catSymbol").value) || null; resetCatalogMapping(); catalogSelectionFacts(); };
$("catFootprint").onchange = () => { CATSEL.footprint = CATSEL.footprints.find(x => x.lib_id === $("catFootprint").value) || null; resetCatalogMapping(); catalogSelectionFacts(); };
function catalogPins() {
    return (CATSEL.symbol?.catalog_selection.pins || []).filter((p, i, a) => a.findIndex(x => x.number === p.number) === i);
}
function resetCatalogMapping() {
    CATSEL.mapping = new Map();
    $("catReviewed").checked = false;
    $("catCopyState").textContent = "";
    const box = $("catMap");
    box.innerHTML = "";
    const prefix = CATSEL.symbol?.catalog_selection.reference || "U";
    $("catReference").value = (/^[A-Za-z][A-Za-z0-9_]*$/.test(prefix) ? prefix : "U") + "1";
    for (const pin of catalogPins()) {
        const label = document.createElement("label"), input = document.createElement("input");
        label.textContent = `Pin ${pin.number}: ${pin.name} (${pin.type}) → pads`;
        input.dataset.pin = pin.number;
        input.setAttribute("aria-label", `Pads for pin ${pin.number}`);
        input.placeholder = "e.g. 1 or 2, 3";
        input.oninput = () => { CATSEL.mapping.set(pin.number, input.value.split(",").map(v => v.trim()).filter(Boolean)); $("catReviewed").checked = false; updateCatalogSnippet(); };
        label.appendChild(input);
        box.appendChild(label);
    }
}
function catalogMapErrors() {
    const pins = catalogPins(), pads = CATSEL.footprint?.catalog_selection.pad_numbers || [], used = new Set(), errors = [];
    if (!CATSEL.validFilters || !CATSEL.candidates.includes(CATSEL.footprint?.lib_id) || !CATSEL.symbolCandidates.includes(CATSEL.symbol?.lib_id))
        errors.push("The selected definitions are outside the current valid filters.");
    if (!pins.length || !pads.length)
        errors.push("Select definitions with electrical pins and numbered pads.");
    for (const pin of pins) {
        const targets = CATSEL.mapping.get(pin.number) || [];
        if (!targets.length)
            errors.push(`Pin ${pin.number} has no pad.`);
        for (const target of targets) {
            if (!pads.includes(target))
                errors.push(`Pin ${pin.number}: unknown pad ${target}.`);
            if (used.has(target))
                errors.push(`Pad ${target} is assigned more than once.`);
            used.add(target);
        }
    }
    const missing = pads.filter(n => !used.has(n));
    if (missing.length)
        errors.push(`Unmapped numbered pads: ${missing.join(", ")}.`);
    if (!/^[A-Za-z][A-Za-z0-9_]*[0-9]$/.test($("catReference").value.trim()))
        errors.push("Use a reference such as R1 or U12.");
    return errors;
}
function catalogPython() {
    const s = CATSEL.symbol, f = CATSEL.footprint, q = value => JSON.stringify(value);
    const map = Object.fromEntries(catalogPins().map(pin => { const pads = CATSEL.mapping.get(pin.number); return [pin.number, pads.length === 1 ? pads[0] : pads]; }));
    return `from fenolite.dsl import Part\n\npart = Part(\n    ${q($("catReference").value.trim())},\n    ${q(s.lib_id)},\n    footprint=${q(f.lib_id)},\n    value=${q($("catValue").value)},\n    pad_map=${JSON.stringify(map)},\n)\n\n# Add part to your Design and connect its pins before building.\n`;
}
function updateCatalogSnippet() {
    const selected = Boolean(CATSEL.symbol && CATSEL.footprint);
    $("catMapping").hidden = !selected;
    const errors = selected ? catalogMapErrors() : [];
    $("catReviewed").disabled = !selected || errors.length > 0;
    const ready = selected && !errors.length && $("catReviewed").checked;
    $("catMapState").textContent = !selected ? "Select both definitions to review their map." : errors.length ? errors.join(" ") : "Map structure is complete. Verify the actual part's datasheet before confirming; catalog evidence remains INFERRED.";
    $("catSnippet").hidden = !ready;
    $("catSnippet").value = ready ? catalogPython() : "";
    $("catCopy").disabled = $("catDownload").disabled = !ready;
    $("catCopyState").textContent = "";
}
$("catEqualNumbers").onclick = () => {
    const pads = CATSEL.footprint?.catalog_selection.pad_numbers || [];
    for (const input of $("catMap").querySelectorAll("input")) {
        const number = input.dataset.pin;
        input.value = pads.includes(number) ? number : "";
        CATSEL.mapping.set(number, input.value ? [input.value] : []);
    }
    $("catReviewed").checked = false;
    updateCatalogSnippet();
};
$("catReviewed").onchange = updateCatalogSnippet;
$("catReference").oninput = $("catValue").oninput = updateCatalogSnippet;
$("catCopy").onclick = async () => {
    if ($("catCopy").disabled)
        return;
    try {
        await navigator.clipboard.writeText($("catSnippet").value);
        $("catCopyState").textContent = "Python copied.";
    }
    catch (e) {
        $("catSnippet").focus();
        $("catSnippet").select();
        $("catCopyState").textContent = "Clipboard unavailable; copy the selected code directly.";
    }
};
$("catDownload").onclick = () => { if (!$("catDownload").disabled)
    download($("catSnippet").value, "component.py", "text/x-python"); };
// ---- board/overlays.ts
// findings: an item of a group drawn as a line, a path (a dashed creepage path too) or a marker; the group's box hides it
const ovGroup = o => o.group || (o.kind === "creepage" ? "analyze_creepage" : "analyze_clearance");
function drawOverlays() {
    if (!S.overlays || !S.overlays.length)
        return;
    worldTf();
    ctx.globalAlpha = 1;
    S.overlays.forEach((o, i) => {
        if (st.ovOff.has(ovGroup(o)))
            return;
        const sel = i === st.selOv, u = 1 / view.s;
        ctx.strokeStyle = o.color;
        ctx.lineWidth = (sel ? 4 : 2.5) * u;
        ctx.setLineDash(o.kind === "creepage" ? [5 * u, 3 * u] : []);
        if (o.pts.length > 1) {
            ctx.beginPath();
            o.pts.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]));
            ctx.stroke();
        }
        ctx.setLineDash([]);
        const p = o.kind === "path" && o.pts.length === 3 ? o.pts[1] : o.pts[0], r = (sel ? 9 : 6) * u;
        ctx.beginPath();
        ctx.arc(p[0], p[1], r, 0, 2 * Math.PI);
        ctx.stroke();
        if (o.kind === "point") {
            ctx.beginPath();
            for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
                ctx.moveTo(p[0] + dx * 0.5 * r, p[1] + dy * 0.5 * r);
                ctx.lineTo(p[0] + dx * 1.8 * r, p[1] + dy * 1.8 * r);
            }
            ctx.stroke();
        }
        if (sel && o.bbox) {
            const b = o.bbox;
            ctx.lineWidth = 1.5 * u;
            ctx.setLineDash([6 * u, 4 * u]);
            ctx.strokeRect(b[0], b[1], b[2] - b[0], b[3] - b[1]);
            ctx.setLineDash([]);
        }
    });
}
// ---- measure/snap.ts
function snapPoints() {
    if (S.__snaps)
        return S.__snaps;
    const out = [];
    if (S.kind === "schematic") {
        for (const p of S.prims) {
            if (p.p && p.k !== "t")
                for (let i = 0; i < p.p.length; i += 2)
                    out.push(p.p[i], p.p[i + 1]);
            else if (p.k === "e" || p.k === "a" || p.k === "t")
                out.push(p.x, p.y);
            else if (p.b)
                out.push(p.b[0], p.b[1], p.b[2], p.b[3]);
        }
    }
    else {
        for (const p of S.pads || [])
            out.push(p.x, p.y);
        for (const pr of S.prims) {
            const d = pr[2];
            if (pr[1] === "s")
                out.push(d[0], d[1], d[2], d[3]);
            else if (pr[1] === "a")
                out.push(d[0], d[1], d[4], d[5]);
            else if (pr[1] === "c")
                out.push(d[0], d[1]);
            else if (pr[1] === "l")
                for (let i = 1; i + 1 < d.length; i += 2)
                    out.push(d[i], d[i + 1]);
            else if ((pr[1] === "p" || pr[1] === "o") && d.length === 1 && d[0].length <= 128)
                for (let i = 0; i < d[0].length; i += 2)
                    out.push(d[0][i], d[0][i + 1]);
        }
    }
    S.__snaps = out;
    return out;
}
function snap(x, y, free) {
    if (free)
        return { p: [x, y], snapped: false }; // Alt held: no snap (change c0193)
    const pts = snapPoints(), tol = 8 / view.s;
    let best = null, bd = tol;
    for (let i = 0; i < pts.length; i += 2) {
        const d = Math.hypot(pts[i] - x, pts[i + 1] - y);
        if (d < bd) {
            bd = d;
            best = [pts[i], pts[i + 1]];
        }
    }
    if (best)
        return { p: best, snapped: true };
    const e = S.kind ? null : snapEdge(x, y, 10);
    return e ? { p: [e.x, e.y], snapped: true, edge: e.label } : { p: [x, y], snapped: false };
}
// ================================================================== edge snap (change c0193)
// Without a point within reach, a board measurement snaps to the nearest point of an edge of a visible layer: pad
// and fill borders, track borders and axis, circles, outlines and the board edge.
const SNAP_CELL = 2;
function buildEdges() {
    const E = [], C = [], grid = new Map();
    const put = (x0, y0, x1, y1, ref) => {
        for (let i = Math.floor(x0 / SNAP_CELL); i <= Math.floor(x1 / SNAP_CELL); i++)
            for (let j = Math.floor(y0 / SNAP_CELL); j <= Math.floor(y1 / SNAP_CELL); j++) {
                const k = i + "," + j;
                let c = grid.get(k);
                if (!c) {
                    c = [];
                    grid.set(k, c);
                }
                c.push(ref);
            }
    };
    const seg = (x1, y1, x2, y2, label) => { E.push([x1, y1, x2, y2, label]); put(Math.min(x1, x2), Math.min(y1, y2), Math.max(x1, x2), Math.max(y1, y2), ["e", E.length - 1]); };
    const circ = (cx, cy, r, label) => { C.push([cx, cy, r, label]); put(cx - r, cy - r, cx + r, cy + r, ["c", C.length - 1]); };
    const poly = (flat, label) => { for (let i = 0; i + 3 < flat.length; i += 2)
        seg(flat[i], flat[i + 1], flat[i + 2], flat[i + 3], `edge · ${label}`); };
    for (const [l] of order()) {
        for (const [pr] of byLayer.get(l.id) || []) {
            const d = pr[2], name = pr[5] || l.name;
            if (pr[1] === "c")
                circ(d[0], d[1], d[2], `edge · ${name}`);
            else if (pr[1] === "s") {
                const w = d[4] / 2, dx = d[2] - d[0], dy = d[3] - d[1], n = Math.hypot(dx, dy) || 1, ox = -dy / n * w, oy = dx / n * w;
                seg(d[0], d[1], d[2], d[3], `axis · ${name}`);
                if (w > 0.05) {
                    seg(d[0] + ox, d[1] + oy, d[2] + ox, d[3] + oy, `edge · ${name}`);
                    seg(d[0] - ox, d[1] - oy, d[2] - ox, d[3] - oy, `edge · ${name}`);
                    circ(d[0], d[1], w, `edge · ${name}`);
                    circ(d[2], d[3], w, `edge · ${name}`);
                }
            }
            else if (pr[1] === "a") {
                const a = pr[6];
                if (!a)
                    continue;
                const T = 2 * Math.PI;
                let span = ((a.a3 - a.a1) % T + T) % T;
                if (a.ccw)
                    span -= T;
                const n = Math.max(6, Math.ceil(Math.abs(span) / 0.15));
                for (const [r, lab] of [[a.r, "axis"], [a.r + d[6] / 2, "edge"], [a.r - d[6] / 2, "edge"]]) {
                    if (r <= 0)
                        continue;
                    for (let k = 0; k < n; k++) {
                        const t0 = a.a1 + span * k / n, t1 = a.a1 + span * (k + 1) / n;
                        seg(a.cx + r * Math.cos(t0), a.cy + r * Math.sin(t0), a.cx + r * Math.cos(t1), a.cy + r * Math.sin(t1), `${lab} · ${name}`);
                    }
                }
            }
            else if (pr[1] === "l")
                poly(d.slice(1), name);
            else if (pr[1] === "p" || pr[1] === "o")
                for (const r of d)
                    poly([...r, r[0], r[1]], name);
        }
    }
    for (const r of S.board) {
        const pts = ringSamples(r).flat();
        poly([...pts, pts[0], pts[1]], "board edge");
    }
    return { E, C, grid };
}
function snapEdge(x, y, tolPx) {
    const key = order().map(e => e[0].id).join("|");
    if (!S.__edges || S.__edgeKey !== key) {
        S.__edgeKey = key;
        S.__edges = buildEdges();
    }
    const tol = tolPx / view.s, sn = S.__edges, seen = new Set();
    let be = null, bed = tol;
    for (let i = Math.floor((x - tol) / SNAP_CELL); i <= Math.floor((x + tol) / SNAP_CELL); i++)
        for (let j = Math.floor((y - tol) / SNAP_CELL); j <= Math.floor((y + tol) / SNAP_CELL); j++) {
            for (const ref of sn.grid.get(i + "," + j) || []) {
                const k = ref[0] + ref[1];
                if (seen.has(k))
                    continue;
                seen.add(k);
                if (ref[0] === "e") {
                    const e = sn.E[ref[1]], dx = e[2] - e[0], dy = e[3] - e[1], L = dx * dx + dy * dy;
                    let t = L ? ((x - e[0]) * dx + (y - e[1]) * dy) / L : 0;
                    t = Math.max(0, Math.min(1, t));
                    const qx = e[0] + t * dx, qy = e[1] + t * dy, dd = Math.hypot(qx - x, qy - y);
                    if (dd < bed) {
                        bed = dd;
                        be = { x: qx, y: qy, label: e[4] };
                    }
                }
                else {
                    const c = sn.C[ref[1]], r0 = Math.hypot(x - c[0], y - c[1]) || 1e-9, dd = Math.abs(r0 - c[2]);
                    if (dd < bed) {
                        bed = dd;
                        be = { x: c[0] + (x - c[0]) * c[2] / r0, y: c[1] + (y - c[1]) * c[2] / r0, label: c[3] };
                    }
                }
            }
        }
    return be;
}
// ---- measure/measure.ts
function drawMeasure() {
    if (!st.measure && !st.mpts.length)
        return;
    worldTf();
    ctx.globalAlpha = 1;
    const C = "#00e08a";
    ctx.strokeStyle = C;
    ctx.lineWidth = 1.5 / view.s;
    const mark = (q, on) => { const r = 4 / view.s; ctx.strokeRect(q[0] - r, q[1] - r, 2 * r, 2 * r); if (on) {
        ctx.beginPath();
        ctx.moveTo(q[0] - 2 * r, q[1]);
        ctx.lineTo(q[0] + 2 * r, q[1]);
        ctx.moveTo(q[0], q[1] - 2 * r);
        ctx.lineTo(q[0], q[1] + 2 * r);
        ctx.stroke();
    } };
    if (st.mhover) {
        mark(st.mhover.p, st.mhover.snapped);
        if (st.mhover.edge && !st.mpts.length)
            $("coord").textContent = `snap: ${st.mhover.edge}`;
    }
    if (!st.mpts.length)
        return;
    const a = st.mpts[0], b = st.mpts[1] || (st.mhover && st.mhover.p);
    mark(a, true);
    if (!b)
        return;
    ctx.beginPath();
    ctx.moveTo(a[0], a[1]);
    ctx.lineTo(b[0], b[1]);
    ctx.stroke();
    if (st.mpts[1])
        mark(b, true);
    const d = Math.hypot(b[0] - a[0], b[1] - a[1]), txt = `${fmtLen(d)}   Δx ${fmtLen(Math.abs(b[0] - a[0]))}   Δy ${fmtLen(Math.abs(b[1] - a[1]))}`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const P = w2s(b[0], b[1]);
    ctx.font = "600 13px system-ui";
    const w = ctx.measureText(txt).width;
    ctx.fillStyle = "#000c";
    ctx.fillRect(P[0] + 8, P[1] - 28, w + 12, 20);
    ctx.fillStyle = C;
    ctx.fillText(txt, P[0] + 14, P[1] - 13);
    worldTf();
    $("coord").textContent = `measure: ${txt}`;
}
function measureClick(X, Y, free) { const [x, y] = s2w(X, Y), q = snap(x, y, free).p; if (st.mpts.length >= 2)
    st.mpts = []; st.mpts.push(q); draw(); }
// ---- board/hit.ts
// ================================================================== hit test (2D)
function segDist(px, py, x1, y1, x2, y2) {
    const dx = x2 - x1, dy = y2 - y1, L = dx * dx + dy * dy;
    let t = L ? ((px - x1) * dx + (py - y1) * dy) / L : 0;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(px - x1 - t * dx, py - y1 - t * dy);
}
function inRing(px, py, r) {
    let c = false;
    for (let i = 0, j = r.length - 2; i < r.length; j = i, i += 2) {
        const xi = r[i], yi = r[i + 1], xj = r[j], yj = r[j + 1];
        if (((yi > py) !== (yj > py)) && (px < (xj - xi) * (py - yi) / (yj - yi) + xi))
            c = !c;
    }
    return c;
}
function hitPrim(pr, x, y, tol) {
    const d = pr[2];
    switch (pr[1]) {
        case "s": return segDist(x, y, d[0], d[1], d[2], d[3]) <= d[4] / 2 + tol;
        case "c": return Math.hypot(x - d[0], y - d[1]) <= d[2] + tol;
        case "l":
            for (let i = 1; i + 3 < d.length; i += 2)
                if (segDist(x, y, d[i], d[i + 1], d[i + 2], d[i + 3]) <= d[0] / 2 + tol)
                    return true;
            return d.length === 3 && Math.hypot(x - d[1], y - d[2]) <= d[0] / 2 + tol;
        case "a": {
            const a = pr[6];
            if (!a)
                return segDist(x, y, d[0], d[1], d[4], d[5]) <= d[6] / 2 + tol;
            if (Math.abs(Math.hypot(x - a.cx, y - a.cy) - a.r) > d[6] / 2 + tol)
                return false;
            const T = 2 * Math.PI, t = Math.atan2(y - a.cy, x - a.cx);
            let span = ((a.a3 - a.a1) % T + T) % T, at = ((t - a.a1) % T + T) % T;
            if (a.ccw) {
                span = T - span;
                at = ((a.a1 - t) % T + T) % T;
            }
            return at <= span;
        }
        case "p":
        case "h": {
            let n = 0;
            for (const r of d)
                if (inRing(x, y, r))
                    n++;
            return n % 2 === 1;
        }
        case "o":
            for (const r of d)
                for (let i = 0; i < r.length; i += 2) {
                    const j = (i + 2) % r.length;
                    if (segDist(x, y, r[i], r[i + 1], r[j], r[j + 1]) <= tol)
                        return true;
                }
            return false;
    }
    return false;
}
function pick(X, Y) {
    const [x, y] = s2w(X, Y), tol = 3 / view.s;
    const layers = order().map(e => e[0]).reverse().filter(l => l.id !== "View.Drill" && l.id !== "View.Outline");
    const outl = (l) => l.id === "View.ZoneOutline" || l.id === "View.ZoneEdge";
    layers.sort((a, b) => outl(a) - outl(b)); // copper before zone outlines
    for (const l of layers) {
        for (const [pr, b] of byLayer.get(l.id) || []) {
            if (x < b[0] - tol || x > b[2] + tol || y < b[1] - tol || y > b[3] + tol)
                continue;
            if (hitPrim(pr, x, y, tol))
                return { layer: l, pr };
        }
    }
    return null;
}
// ---- board/query.ts
// ---- query (c0187): the board filter. key:value terms joined by spaces (and), "|" (or), a leading "-" (not),
// * and ? wildcards, quoted values. Keys: net, ref, footprint, value, layer, side; any other key is the name of a
// part parameter; a bare value matches a reference or a net. Pure functions of a scene, run in Node by the tests.
function wildRe(v) { return new RegExp("^" + String(v).replace(/[.+^${}()[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".") + "$", "i"); }
function queryParse(text) {
    const s = String(text), groups = [[]];
    let i = 0;
    while (i < s.length) {
        if (/\s/.test(s[i])) {
            i++;
            continue;
        }
        if (s[i] === "|") {
            groups.push([]);
            i++;
            continue;
        }
        let neg = false, key = "", val;
        if (s[i] === "-") {
            neg = true;
            i++;
        }
        let j = i;
        while (j < s.length && /[\w.]/.test(s[j]))
            j++;
        if (j > i && s[j] === ":") {
            key = s.slice(i, j).toLowerCase();
            i = j + 1;
        }
        if (s[i] === "\"") {
            const e = s.indexOf("\"", i + 1);
            val = s.slice(i + 1, e < 0 ? s.length : e);
            i = e < 0 ? s.length : e + 1;
        }
        else {
            j = i;
            while (j < s.length && !/[\s|]/.test(s[j]))
                j++;
            val = s.slice(i, j);
            i = j;
        }
        groups[groups.length - 1].push({ key, neg, val, re: wildRe(val) });
    }
    return groups.filter(g => g.length);
}
function termTest(t, c) {
    const any = vs => vs.some(v => v != null && v !== "" && t.re.test(String(v)));
    let hit;
    if (t.key === "")
        hit = any([c.ref, ...c.nets]);
    else if (t.key === "net")
        hit = any(c.nets);
    else if (t.key === "layer")
        hit = any(c.layers);
    else if (t.key === "ref" || t.key === "footprint" || t.key === "value" || t.key === "side")
        hit = any([c[t.key]]);
    else {
        const p = c.params || {}, k = Object.keys(p).find(n => n.toLowerCase() === t.key);
        hit = k !== undefined && any([p[k]]);
    }
    return hit !== t.neg;
}
function queryTest(q, c) { return q.some(g => g.every(t => termTest(t, c))); }
function queryRun(sc, q) {
    const lt = new Map(sc.layers.map(l => [l.id, { tags: [l.id, l.name], side: l.side }]));
    const cn = sc.comps.map(() => new Set()), cl = sc.comps.map(() => new Set()), prims = new Set();
    for (const pr of sc.prims) {
        const L = lt.get(pr[0]) || { tags: [pr[0]], side: "" }, c = pr[4] >= 0 ? sc.comps[pr[4]] : null, net = pr[3] >= 0 ? sc.nets[pr[3]] : "";
        if (c) {
            if (net)
                cn[pr[4]].add(net);
            for (const t of L.tags)
                cl[pr[4]].add(t);
        }
        const ctx = { nets: net ? [net] : [], layers: L.tags, ref: c ? c.ref : "", footprint: c ? c.footprint : "", value: c ? c.value : "",
            side: c ? c.side : L.side || "", params: c ? c.params : null };
        if (queryTest(q, ctx))
            prims.add(pr);
    }
    const comps = [];
    sc.comps.forEach((c, i) => { if (queryTest(q, { nets: [...cn[i]], layers: [...cl[i]], ref: c.ref, footprint: c.footprint, value: c.value, side: c.side, params: c.params }))
        comps.push(i); });
    return { prims, comps };
}
function similarQuery(sc, pr, ci) {
    const qv = v => `"${String(v).replace(/"/g, "")}"`;
    if (ci >= 0) {
        const c = sc.comps[ci];
        return `footprint:${qv(c.footprint)}` + (c.value ? ` value:${qv(c.value)}` : "");
    }
    if (!pr)
        return "";
    const l = sc.layers.find(x => x.id === pr[0]), layer = `layer:${qv(l ? l.name : pr[0])}`;
    return pr[3] >= 0 ? `net:${qv(sc.nets[pr[3]])} ${layer}` : layer;
}
// ---- end query
// ---- measure/edge.ts
// ---- edge (c0189): the shortest distance between the edges of two board primitives, as Altium's clearance
// measure gives it. A primitive is segments and points grown by a radius (a track: its centre line and half its
// width; a via or a round pad: its centre and radius; an arc: its centre line sampled every 2°) or filled rings
// (pads, fills, regions). The distance is exact for segments and points; overlapping shapes read 0.
function arcSample(d) {
    const [x1, y1, x2, y2, x3, y3] = d, D = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2));
    if (Math.abs(D) < 1e-12)
        return [x1, y1, x3, y3];
    const s1 = x1 * x1 + y1 * y1, s2 = x2 * x2 + y2 * y2, s3 = x3 * x3 + y3 * y3;
    const cx = (s1 * (y2 - y3) + s2 * (y3 - y1) + s3 * (y1 - y2)) / D, cy = (s1 * (x3 - x2) + s2 * (x1 - x3) + s3 * (x2 - x1)) / D, r = Math.hypot(x1 - cx, y1 - cy);
    const T = 2 * Math.PI, a1 = Math.atan2(y1 - cy, x1 - cx), a2 = Math.atan2(y2 - cy, x2 - cx), a3 = Math.atan2(y3 - cy, x3 - cx);
    const ccwSpan = ((a3 - a1) % T + T) % T, midIn = ((a2 - a1) % T + T) % T <= ccwSpan, span = midIn ? ccwSpan : ccwSpan - T;
    const n = Math.max(2, Math.ceil(Math.abs(span) / (Math.PI / 90))), out = [];
    for (let i = 0; i <= n; i++) {
        const t = a1 + span * i / n;
        out.push(cx + r * Math.cos(t), cy + r * Math.sin(t));
    }
    return out;
}
function edgeShape(pr) {
    const d = pr[2];
    switch (pr[1]) {
        case "s": return { lines: [[d[0], d[1], d[2], d[3]]], rings: [], r: d[4] / 2 };
        case "c": return { lines: [[d[0], d[1]]], rings: [], r: d[2] };
        case "a": return { lines: [arcSample(d)], rings: [], r: d[6] / 2 };
        case "l": return { lines: [d.slice(1)], rings: [], r: d[0] / 2 };
        case "p":
        case "h": return { lines: d, rings: d, r: 0, closed: true };
        case "o": return { lines: d, rings: [], r: 0, closed: true };
    }
    return null;
}
function ptSeg(px, py, x1, y1, x2, y2) {
    const dx = x2 - x1, dy = y2 - y1, L = dx * dx + dy * dy;
    let t = L ? ((px - x1) * dx + (py - y1) * dy) / L : 0;
    t = Math.max(0, Math.min(1, t));
    const qx = x1 + t * dx, qy = y1 + t * dy;
    return [Math.hypot(px - qx, py - qy), qx, qy];
}
function segSeg(a, b) {
    const [ax, ay, bx, by] = a, [cx, cy, dx, dy] = b, cross = (px, py, qx, qy, rx, ry) => (qx - px) * (ry - py) - (qy - py) * (rx - px);
    const d1 = cross(cx, cy, dx, dy, ax, ay), d2 = cross(cx, cy, dx, dy, bx, by), d3 = cross(ax, ay, bx, by, cx, cy), d4 = cross(ax, ay, bx, by, dx, dy);
    if (((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))) {
        const t = d1 / (d1 - d2), x = ax + t * (bx - ax), y = ay + t * (by - ay);
        return [0, [x, y], [x, y]];
    }
    let best = null;
    for (const [p, q, flip] of [[[ax, ay], b, false], [[bx, by], b, false], [[cx, cy], a, true], [[dx, dy], a, true]]) {
        const [dd, qx, qy] = ptSeg(p[0], p[1], q[0], q[1], q[2], q[3]);
        if (!best || dd < best[0])
            best = flip ? [dd, [qx, qy], p] : [dd, p, [qx, qy]];
    }
    return best;
}
function edgeSegs(sh) {
    const out = [];
    for (const l of sh.lines) {
        const n = l.length / 2;
        if (n === 1)
            out.push([l[0], l[1], l[0], l[1]]);
        for (let i = 0; i + 1 < n; i++)
            out.push([l[2 * i], l[2 * i + 1], l[2 * i + 2], l[2 * i + 3]]);
        if (sh.closed && n > 2)
            out.push([l[2 * n - 2], l[2 * n - 1], l[0], l[1]]);
    }
    return out;
}
function ringHas(rings, x, y) {
    let n = 0;
    for (const r of rings) {
        let c = false;
        for (let i = 0, j = r.length - 2; i < r.length; j = i, i += 2)
            if ((r[i + 1] > y) !== (r[j + 1] > y) && x < (r[j] - r[i]) * (y - r[i + 1]) / (r[j + 1] - r[i + 1]) + r[i])
                c = !c;
        if (c)
            n++;
    }
    return n % 2 === 1;
}
function edgeDistance(pa, pb) {
    const A = edgeShape(pa), B = edgeShape(pb);
    if (!A || !B)
        return null;
    let best = null;
    for (const s of edgeSegs(A))
        for (const t of edgeSegs(B)) {
            const r = segSeg(s, t);
            if (!best || r[0] < best[0])
                best = r;
        }
    if (!best)
        return null;
    const [d, p, q] = best, gap = d - A.r - B.r;
    if (gap <= 0)
        return { d: 0, a: p, b: q };
    for (const [S, T] of [[A, B], [B, A]])
        if (S.rings.length) {
            const l = T.lines[0];
            if (l && ringHas(S.rings, l[0], l[1]))
                return { d: 0, a: [l[0], l[1]], b: [l[0], l[1]] };
        }
    const ux = (q[0] - p[0]) / d, uy = (q[1] - p[1]) / d; // the centre-line points moved out to each edge
    return { d: gap, a: [p[0] + ux * A.r, p[1] + uy * A.r], b: [q[0] - ux * B.r, q[1] - uy * B.r] };
}
function edgeBetween(ga, gb) {
    let best = null;
    for (const a of ga)
        for (const b of gb) {
            const r = edgeDistance(a, b);
            if (r && (!best || r.d < best.d))
                best = r;
        }
    return best;
}
// ---- end edge
// ---- board/variants.ts
// ================================================================== assembly variants of an Altium project (c0186)
let VARIANT = null;
function variantOf(ref) { const v = VARIANT && S && S.variants && S.variants[VARIANT]; return v ? v[ref] || null : null; }
function notFitted(ref) { const v = variantOf(ref); return !!(v && v.kind === "not fitted"); }
function variantNames() { return S && S.variants ? Object.keys(S.variants) : []; }
function buildVariants() {
    if (S && S.variant && VARIANT === null)
        VARIANT = S.variant;
    refreshToolbar();
}
function setVariant(v) { VARIANT = v || null; if (V3.built) {
    rebuildBodies();
} draw(); if (st.mode3d)
    draw3D(); }
function drawVariantMarks(boxes) {
    if (!VARIANT)
        return;
    ctx.globalAlpha = 1;
    ctx.strokeStyle = "#ff3030";
    ctx.lineWidth = 2 / view.s;
    for (const [ref, b] of boxes) {
        if (!b || !notFitted(ref))
            continue;
        ctx.beginPath();
        ctx.moveTo(b[0], b[1]);
        ctx.lineTo(b[2], b[3]);
        ctx.moveTo(b[2], b[1]);
        ctx.lineTo(b[0], b[3]);
        ctx.stroke();
    }
}
// ---- board/info.ts
function compInfo(ci) { return partModel(ci); } // c0301: the inspector model of a part
function padOf(label, x, y) {
    let best = null, bd = Infinity;
    for (const p of S.pads || []) {
        if (p.label !== label.replace(/ (hole|slot)$/, ""))
            continue;
        const d = Math.hypot(p.x - x, p.y - y);
        if (d < bd) {
            bd = d;
            best = p;
        }
    }
    return best;
}
function layerName(id) { const l = S.layers.find(x => x.id === id); return l ? l.name : id; }
function padInfo(p) { return padSection(p, FMT, layerName); } // c0301: the Pad section of the inspector (c0181: an Altium pad's mask and paste)
function select(h, at) {
    st.selFinding = -1;
    st.selNet = -1;
    st.selComp = -1;
    st.lastHit = h;
    st.lastAt = at;
    if (!h) {
        showInfo(null);
        draw();
        return;
    }
    const pr = h.pr, net = pr[3], ci = pr[4];
    if (net >= 0) {
        st.selNet = net;
        shareNet(S.nets[net]);
    }
    if (ci >= 0 && net < 0)
        st.selComp = ci;
    inspect(() => boardModel(h, at));
    draw();
}
// ---- three/math.ts
function mul(a, b) { const o = new Array(16); for (let i = 0; i < 4; i++)
    for (let j = 0; j < 4; j++) {
        let s = 0;
        for (let k = 0; k < 4; k++)
            s += a[k * 4 + j] * b[i * 4 + k];
        o[i * 4 + j] = s;
    } return o; }
function persp(f, a, n, fa) { const t = 1 / Math.tan(f / 2); return [t / a, 0, 0, 0, 0, t, 0, 0, 0, 0, (fa + n) / (n - fa), -1, 0, 0, 2 * fa * n / (n - fa), 0]; }
function lookAt(e, c, u) {
    let z = [e[0] - c[0], e[1] - c[1], e[2] - c[2]];
    let l = Math.hypot(...z);
    z = z.map(v => v / l);
    let x = [u[1] * z[2] - u[2] * z[1], u[2] * z[0] - u[0] * z[2], u[0] * z[1] - u[1] * z[0]];
    l = Math.hypot(...x) || 1;
    x = x.map(v => v / l);
    const y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]];
    return [x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0, -(x[0] * e[0] + x[1] * e[1] + x[2] * e[2]), -(y[0] * e[0] + y[1] * e[1] + y[2] * e[2]), -(z[0] * e[0] + z[1] * e[1] + z[2] * e[2]), 1];
}
function inv(a) {
    const o = new Array(16);
    const b00 = a[0] * a[5] - a[1] * a[4], b01 = a[0] * a[6] - a[2] * a[4], b02 = a[0] * a[7] - a[3] * a[4], b03 = a[1] * a[6] - a[2] * a[5], b04 = a[1] * a[7] - a[3] * a[5], b05 = a[2] * a[7] - a[3] * a[6];
    const b06 = a[8] * a[13] - a[9] * a[12], b07 = a[8] * a[14] - a[10] * a[12], b08 = a[8] * a[15] - a[11] * a[12], b09 = a[9] * a[14] - a[10] * a[13], b10 = a[9] * a[15] - a[11] * a[13], b11 = a[10] * a[15] - a[11] * a[14];
    const det = 1 / (b00 * b11 - b01 * b10 + b02 * b09 + b03 * b08 - b04 * b07 + b05 * b06);
    o[0] = (a[5] * b11 - a[6] * b10 + a[7] * b09) * det;
    o[1] = (a[2] * b10 - a[1] * b11 - a[3] * b09) * det;
    o[2] = (a[13] * b05 - a[14] * b04 + a[15] * b03) * det;
    o[3] = (a[10] * b04 - a[9] * b05 - a[11] * b03) * det;
    o[4] = (a[6] * b08 - a[4] * b11 - a[7] * b07) * det;
    o[5] = (a[0] * b11 - a[2] * b08 + a[3] * b07) * det;
    o[6] = (a[14] * b02 - a[12] * b05 - a[15] * b01) * det;
    o[7] = (a[8] * b05 - a[10] * b02 + a[11] * b01) * det;
    o[8] = (a[4] * b10 - a[5] * b08 + a[7] * b06) * det;
    o[9] = (a[1] * b08 - a[0] * b10 - a[3] * b06) * det;
    o[10] = (a[12] * b04 - a[13] * b02 + a[15] * b00) * det;
    o[11] = (a[9] * b02 - a[8] * b04 - a[11] * b00) * det;
    o[12] = (a[5] * b07 - a[4] * b09 - a[6] * b06) * det;
    o[13] = (a[0] * b09 - a[1] * b07 + a[2] * b06) * det;
    o[14] = (a[13] * b01 - a[12] * b03 - a[14] * b00) * det;
    o[15] = (a[8] * b03 - a[9] * b01 + a[10] * b00) * det;
    return o;
}
// ---- three/view3d.ts
// ================================================================== 3D view (WebGL, no library)
const glc = $("gl");
const LIGHT = { ambient: "0.30", key: "0.55", fill: "0.20" }; // c0301: the terms of the 3D lighting (GLSL literals)
const V3 = {
    gl: null, prog: null, loc: {}, parts: [], tex: {}, built: false, cam: { yaw: -2.2, pitch: 0.75, dist: 260, tx: 0, ty: 0, tz: 0 }, selBody: -1, bodies: true, bodyPart: null,
    board: true, silk: true, copper: true, anim: 0
}; // c0301: the 3D panel's toggles
function shader(gl, type, src) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS))
        throw new Error(gl.getShaderInfoLog(s));
    return s;
}
function init3D() {
    if (V3.gl)
        return true;
    const gl = glc.getContext("webgl", { antialias: true });
    if (!gl) {
        showInfo("This browser has no WebGL: the 3D view is not available.");
        return false;
    }
    const vs = `attribute vec3 aP; attribute vec3 aN; attribute vec3 aC; attribute vec2 aT; uniform mat4 uM; varying vec3 vN; varying vec3 vC; varying vec2 vT;
    void main(){ gl_Position = uM * vec4(aP, 1.0); vN = aN; vC = aC; vT = aT; }`;
    const fs = `precision mediump float; varying vec3 vN; varying vec3 vC; varying vec2 vT; uniform sampler2D uS; uniform float uTex; uniform vec3 uL; uniform vec3 uL2;
    void main(){ vec4 t = texture2D(uS, vT); if (uTex > 0.5 && t.a < 0.5) discard; vec3 base = uTex > 0.5 ? t.rgb : vC; vec3 n = normalize(vN);
      gl_FragColor = vec4(base * (${LIGHT.ambient} + ${LIGHT.key} * max(dot(n, uL), 0.0) + ${LIGHT.fill} * abs(dot(n, uL2))), 1.0); }`;
    const p = gl.createProgram();
    gl.attachShader(p, shader(gl, gl.VERTEX_SHADER, vs));
    gl.attachShader(p, shader(gl, gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(p);
    V3.gl = gl;
    V3.prog = p;
    for (const k of ["aP", "aN", "aC", "aT"])
        V3.loc[k] = gl.getAttribLocation(p, k);
    for (const k of ["uM", "uS", "uTex", "uL", "uL2"])
        V3.loc[k] = gl.getUniformLocation(p, k);
    // body models (change c0193): per-vertex colour, alpha 0 where the model gives none (the body colour then)
    V3.u32 = !!gl.getExtension("OES_element_index_uint");
    const mvs = `attribute vec3 aP; attribute vec3 aN; attribute vec4 aC; uniform mat4 uVP; uniform mat4 uW; varying vec3 vN; varying vec4 vC;
    void main(){ gl_Position = uVP * uW * vec4(aP, 1.0); vN = (uW * vec4(aN, 0.0)).xyz; vC = aC; }`;
    const mfs = `precision mediump float; varying vec3 vN; varying vec4 vC; uniform vec3 uBody; uniform float uSel; uniform vec3 uL; uniform vec3 uL2;
    void main(){ vec3 base = vC.a > 0.5 ? vC.rgb : uBody; if (uSel > 0.5) base = mix(base, vec3(1.0, 0.85, 0.3), 0.55); vec3 n = normalize(vN);
      gl_FragColor = vec4(base * (${LIGHT.ambient} + ${LIGHT.key} * max(dot(n, uL), 0.0) + ${LIGHT.fill} * abs(dot(n, uL2))), 1.0); }`;
    const q = gl.createProgram();
    gl.attachShader(q, shader(gl, gl.VERTEX_SHADER, mvs));
    gl.attachShader(q, shader(gl, gl.FRAGMENT_SHADER, mfs));
    gl.linkProgram(q);
    V3.mprog = q;
    V3.mloc = {};
    for (const k of ["aP", "aN", "aC"])
        V3.mloc[k] = gl.getAttribLocation(q, k);
    for (const k of ["uVP", "uW", "uBody", "uSel", "uL", "uL2"])
        V3.mloc[k] = gl.getUniformLocation(q, k);
    return true;
}
function b64(text, Type) { const bin = atob(text), u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++)
    u8[i] = bin.charCodeAt(i); return new Type(u8.buffer); }
function buildMeshes() {
    const gl = V3.gl;
    for (const m of Object.values(V3.meshBufs || {}))
        for (const k of ["pos", "nrm", "col", "idx"])
            gl.deleteBuffer(m[k]);
    V3.meshBufs = {};
    for (const [key, ms] of Object.entries(S.meshes || {})) {
        if (!ms)
            continue;
        const P = b64(ms.v, Float32Array), I = b64(ms.i, Uint32Array), C = b64(ms.c, Uint8Array), N = new Float32Array(P.length);
        for (let t = 0; t < I.length; t += 3) {
            const a = I[t] * 3, b = I[t + 1] * 3, c = I[t + 2] * 3;
            const ux = P[b] - P[a], uy = P[b + 1] - P[a + 1], uz = P[b + 2] - P[a + 2], vx = P[c] - P[a], vy = P[c + 1] - P[a + 1], vz = P[c + 2] - P[a + 2];
            const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
            for (const o of [a, b, c]) {
                N[o] += nx;
                N[o + 1] += ny;
                N[o + 2] += nz;
            }
        }
        for (let o = 0; o < N.length; o += 3) {
            const l = Math.hypot(N[o], N[o + 1], N[o + 2]) || 1;
            N[o] /= l;
            N[o + 1] /= l;
            N[o + 2] /= l;
        }
        const buf = (data, target) => { const b = gl.createBuffer(); gl.bindBuffer(target, b); gl.bufferData(target, data, gl.STATIC_DRAW); return b; };
        let idx = I, type = gl.UNSIGNED_INT;
        if (!V3.u32) {
            if (P.length / 3 > 65535)
                continue;
            idx = new Uint16Array(I);
            type = gl.UNSIGNED_SHORT;
        }
        V3.meshBufs[key] = { pos: buf(P, gl.ARRAY_BUFFER), nrm: buf(N, gl.ARRAY_BUFFER), col: buf(C, gl.ARRAY_BUFFER), idx: buf(idx, gl.ELEMENT_ARRAY_BUFFER), n: I.length, type };
    }
}
function hexRGB(h) { const n = parseInt(h.slice(1), 16); return [(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]; }
function makePart(data, tex) {
    const gl = V3.gl, b = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, b);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.STATIC_DRAW);
    return { buf: b, n: data.length / 11, tex };
}
function push(arr, p, n, c, t) { arr.push(p[0], p[1], p[2], n[0], n[1], n[2], c[0], c[1], c[2], t ? t[0] : 0, t ? t[1] : 0); }
function quad(arr, a, b, c2, d, col) {
    const ux = b[0] - a[0], uy = b[1] - a[1], uz = b[2] - a[2], vx = d[0] - a[0], vy = d[1] - a[1], vz = d[2] - a[2];
    const n = [uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx];
    for (const p of [a, b, c2, a, c2, d])
        push(arr, p, n, col);
}
// 3D coordinates: x along the board, y = -board y (so the front face is seen from +z with the board upright), z up
function P3(x, y, z) { return [x, -y, z]; }
function sideTexture(side) {
    const b = S.bounds, w = b[2] - b[0], h = b[3] - b[1], maxT = V3.gl.getParameter(V3.gl.MAX_TEXTURE_SIZE);
    const ppm = Math.min(16, (Math.min(maxT, 8192) - 2) / Math.max(w, h)), cw = Math.ceil(w * ppm), ch = Math.ceil(h * ppm);
    const c = document.createElement("canvas");
    c.width = cw;
    c.height = ch;
    const g = c.getContext("2d");
    g.setTransform(ppm, 0, 0, ppm, -b[0] * ppm, -b[1] * ppm);
    g.fillStyle = "#1d5f33";
    g.fill(boardPath(), "evenodd");
    g.save();
    g.clip(boardPath(), "evenodd");
    const pre = side === "top" ? "F." : "B.";
    const lay = id => S.layers.find(l => l.id === id);
    if (lay(pre + "Cu") && V3.copper)
        paintCache(g, cache.get(pre + "Cu"), pre + "Cu", "#2b8a45", 1, ppm);
    if (lay(pre + "Mask"))
        paintCache(g, cache.get(pre + "Mask"), pre + "Mask", "#d4b05c", 1, ppm);
    if (lay(pre + "SilkS") && V3.silk) {
        paintCache(g, cache.get(pre + "SilkS"), pre + "SilkS", "#f1f1ea", 1, ppm);
        paintTexts(g, pre + "SilkS", "#f1f1ea", 1, ppm);
    }
    if (lay("View.Drill"))
        paintCache(g, cache.get("View.Drill"), "View.Drill", "#0b0b0b", 1, ppm);
    g.restore();
    const gl = V3.gl, t = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, c);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return t;
}
function bodyGeometry(arr, bd, col) {
    const T = S.board3d.thickness, dn = bd.side === "bottom";
    const zA = dn ? -bd.z0 : T + bd.z0, zB = dn ? -bd.z1 : T + bd.z1, ring = [];
    for (let i = 0; i < bd.ring.length; i += 2)
        ring.push([bd.ring[i], bd.ring[i + 1]]);
    const n = ring.length;
    if (n < 3)
        return;
    for (let i = 0; i < n; i++) {
        const a = ring[i], b = ring[(i + 1) % n];
        quad(arr, P3(a[0], a[1], zA), P3(b[0], b[1], zA), P3(b[0], b[1], zB), P3(a[0], a[1], zB), col);
    }
    let cx = 0, cy = 0;
    for (const p of ring) {
        cx += p[0];
        cy += p[1];
    }
    cx /= n;
    cy /= n;
    const cap = col === BODY_RGB ? hexRGB(BODY_TOP) : col.map(v => v + (1 - v) * 0.18);
    for (let i = 0; i < n; i++) {
        const a = ring[i], b = ring[(i + 1) % n];
        for (const p of [[cx, cy], a, b])
            push(arr, P3(p[0], p[1], zB), [0, 0, dn ? -1 : 1], cap);
    }
}
function build3D() {
    if (!init3D())
        return false;
    const gl = V3.gl;
    for (const p of V3.parts)
        gl.deleteBuffer(p.buf);
    V3.parts = [];
    for (const k of Object.keys(V3.tex))
        gl.deleteTexture(V3.tex[k]);
    V3.tex.top = sideTexture("top");
    V3.tex.bottom = sideTexture("bottom");
    const b = S.bounds, w = b[2] - b[0], h = b[3] - b[1], T = S.board3d.thickness;
    const top = [], bot = [], edge = [], corners = [[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]];
    const uv = p => [(p[0] - b[0]) / w, (p[1] - b[1]) / h];
    for (const tri of [[0, 1, 2], [0, 2, 3]]) {
        for (const k of tri)
            push(top, P3(corners[k][0], corners[k][1], T), [0, 0, 1], [1, 1, 1], uv(corners[k]));
        for (const k of [tri[0], tri[2], tri[1]])
            push(bot, P3(corners[k][0], corners[k][1], 0), [0, 0, -1], [1, 1, 1], uv(corners[k]));
    }
    const ec = hexRGB("#a99c62");
    for (const r of S.board) {
        const pts = ringSamples(r);
        for (let i = 0; i < pts.length; i++) {
            const a = pts[i], c2 = pts[(i + 1) % pts.length];
            quad(edge, P3(a[0], a[1], 0), P3(c2[0], c2[1], 0), P3(c2[0], c2[1], T), P3(a[0], a[1], T), ec);
        }
    }
    V3.parts.push(makePart(top, "top"), makePart(bot, "bottom"), makePart(edge, null));
    V3.bodyPart = null;
    buildMeshes();
    rebuildBodies();
    if (!V3.built) {
        V3.cam.tx = (b[0] + b[2]) / 2;
        V3.cam.ty = -(b[1] + b[3]) / 2;
        V3.cam.tz = 0;
        V3.cam.dist = Math.max(w, h) * 1.7;
    }
    V3.built = true;
    return true;
}
const BODY = "#33363c", BODY_TOP = "#5b6069", BODY_SEL = "#ffd84d", MESH_BODY = "#9aa0a8"; // c0301: Fenolite's body colours
const BODY_RGB = hexRGB(BODY);
function rebuildBodies() {
    const gl = V3.gl;
    if (!gl)
        return;
    if (V3.bodyPart)
        gl.deleteBuffer(V3.bodyPart.buf);
    const arr = [];
    (S.bodies || []).forEach((bd, i) => {
        if (notFitted(bd.ref))
            return;
        if (bd.mesh && V3.meshBufs && V3.meshBufs[bd.mesh])
            return;
        const sel = i === V3.selBody || (st.selComp >= 0 && bd.comp === st.selComp);
        bodyGeometry(arr, bd, sel ? hexRGB(BODY_SEL) : BODY_RGB);
    });
    V3.bodyPart = arr.length ? makePart(arr, null) : null;
}
function camEye() { const c = V3.cam; return [c.tx + c.dist * Math.cos(c.pitch) * Math.cos(c.yaw), c.ty + c.dist * Math.cos(c.pitch) * Math.sin(c.yaw), c.tz + c.dist * Math.sin(c.pitch)]; }
function mvp() {
    const c = V3.cam, e = camEye(), up = Math.abs(Math.cos(c.pitch)) < 1e-3 ? [Math.cos(c.yaw + Math.PI), Math.sin(c.yaw + Math.PI), 0] : [0, 0, 1];
    return mul(persp(0.75, Math.max(W, 1) / Math.max(H, 1), c.dist * 0.01, c.dist * 10), lookAt(e, [c.tx, c.ty, c.tz], up));
}
function camBasis() {
    const m = lookAt(camEye(), [V3.cam.tx, V3.cam.ty, V3.cam.tz], Math.abs(Math.cos(V3.cam.pitch)) < 1e-3 ? [Math.cos(V3.cam.yaw + Math.PI), Math.sin(V3.cam.yaw + Math.PI), 0] : [0, 0, 1]);
    return [[m[0], m[4], m[8]], [m[1], m[5], m[9]], [m[2], m[6], m[10]]];
}
function lights() {
    const [r, u, b] = camBasis(), mix = (a, c, d) => { const v = [0, 1, 2].map(i => a * r[i] + c * u[i] + d * b[i]), l = Math.hypot(...v); return v.map(x => x / l); };
    return [mix(-0.45, 0.55, 0.7), mix(0.6, -0.35, 0.4)];
}
function resize3D() { glc.width = Math.max(1, Math.round(W * dpr)); glc.height = Math.max(1, Math.round(H * dpr)); draw3D(); }
function draw3D() {
    if (!V3.built || !st.mode3d)
        return;
    const gl = V3.gl, L = V3.loc;
    gl.viewport(0, 0, glc.width, glc.height);
    gl.clearColor(0.08, 0.09, 0.11, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.enable(gl.DEPTH_TEST);
    gl.useProgram(V3.prog);
    gl.uniformMatrix4fv(L.uM, false, new Float32Array(mvp()));
    const [key, fill] = lights();
    gl.uniform3fv(L.uL, key);
    gl.uniform3fv(L.uL2, fill);
    const parts = V3.board ? [...V3.parts] : [];
    if (V3.bodies && V3.bodyPart)
        parts.push(V3.bodyPart);
    for (const p of parts) {
        gl.bindBuffer(gl.ARRAY_BUFFER, p.buf);
        const F = 44;
        gl.vertexAttribPointer(L.aP, 3, gl.FLOAT, false, F, 0);
        gl.enableVertexAttribArray(L.aP);
        gl.vertexAttribPointer(L.aN, 3, gl.FLOAT, false, F, 12);
        gl.enableVertexAttribArray(L.aN);
        gl.vertexAttribPointer(L.aC, 3, gl.FLOAT, false, F, 24);
        gl.enableVertexAttribArray(L.aC);
        gl.vertexAttribPointer(L.aT, 2, gl.FLOAT, false, F, 36);
        gl.enableVertexAttribArray(L.aT);
        gl.uniform1f(L.uTex, p.tex ? 1 : 0);
        if (p.tex) {
            gl.activeTexture(gl.TEXTURE0);
            gl.bindTexture(gl.TEXTURE_2D, V3.tex[p.tex]);
            gl.uniform1i(L.uS, 0);
        }
        gl.drawArrays(gl.TRIANGLES, 0, p.n);
    }
    for (const k of ["aP", "aN", "aC", "aT"])
        gl.disableVertexAttribArray(L[k]);
    drawCube();
    if (!V3.bodies || !V3.meshBufs)
        return;
    const ML = V3.mloc;
    gl.useProgram(V3.mprog);
    gl.uniformMatrix4fv(ML.uVP, false, new Float32Array(mvp()));
    gl.uniform3fv(ML.uL, key);
    gl.uniform3fv(ML.uL2, fill);
    (S.bodies || []).forEach((bd, i) => {
        const mb = bd.mesh && V3.meshBufs[bd.mesh];
        if (!mb || notFitted(bd.ref))
            return;
        gl.uniformMatrix4fv(ML.uW, false, new Float32Array(bd.m));
        gl.uniform3fv(ML.uBody, hexRGB(MESH_BODY));
        gl.uniform1f(ML.uSel, (i === V3.selBody || (st.selComp >= 0 && bd.comp === st.selComp)) ? 1 : 0);
        gl.bindBuffer(gl.ARRAY_BUFFER, mb.pos);
        gl.vertexAttribPointer(ML.aP, 3, gl.FLOAT, false, 0, 0);
        gl.enableVertexAttribArray(ML.aP);
        gl.bindBuffer(gl.ARRAY_BUFFER, mb.nrm);
        gl.vertexAttribPointer(ML.aN, 3, gl.FLOAT, false, 0, 0);
        gl.enableVertexAttribArray(ML.aN);
        gl.bindBuffer(gl.ARRAY_BUFFER, mb.col);
        gl.vertexAttribPointer(ML.aC, 4, gl.UNSIGNED_BYTE, true, 0, 0);
        gl.enableVertexAttribArray(ML.aC);
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, mb.idx);
        gl.drawElements(gl.TRIANGLES, mb.n, mb.type, 0);
    });
    for (const k of ["aP", "aN", "aC"])
        gl.disableVertexAttribArray(ML[k]);
}
function set3D(on) {
    st.mode3d = on;
    refreshToolbar();
    glc.style.display = on ? "block" : "none";
    cv.style.display = on ? "none" : "block";
    $("cube").style.display = on ? "block" : "none";
    document.body.classList.toggle("mode3d", on);
    refreshDock();
    if (on) {
        measure();
        if (!V3.built && !build3D()) {
            set3D(false);
            return;
        }
        resize3D();
    }
    else {
        setFitted(false);
        resize();
    }
}
const PRESETS = { top: [-Math.PI / 2, 1.5699], bottom: [-Math.PI / 2, -1.5699], front: [-Math.PI / 2, 0], back: [Math.PI / 2, 0], left: [Math.PI, 0], right: [0, 0], iso: [-2.2, 0.75] };
function camPreset(kind, animate = false) {
    const [yaw, pitch] = Array.isArray(kind) ? kind : PRESETS[kind] || PRESETS.iso, c = V3.cam, b = S.bounds;
    const to = { yaw, pitch, tx: (b[0] + b[2]) / 2, ty: -(b[1] + b[3]) / 2, tz: 0, dist: Math.max(b[2] - b[0], b[3] - b[1]) * 1.7 };
    cancelAnimationFrame(V3.anim);
    if (!animate) {
        Object.assign(c, to);
        draw3D();
        return;
    }
    const from = { ...c }, dy = Math.atan2(Math.sin(to.yaw - from.yaw), Math.cos(to.yaw - from.yaw)), t0 = performance.now();
    const step = now => {
        const k = Math.min(1, (now - t0) / 250), e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
        c.yaw = from.yaw + dy * e;
        c.pitch = from.pitch + (to.pitch - from.pitch) * e;
        for (const key of ["tx", "ty", "tz", "dist"])
            c[key] = from[key] + (to[key] - from[key]) * e;
        draw3D();
        if (k < 1)
            V3.anim = requestAnimationFrame(step);
        else
            c.yaw = to.yaw;
    };
    V3.anim = requestAnimationFrame(step);
}
function set3DOption(key, on) {
    V3[key] = on;
    if ((key === "silk" || key === "copper") && V3.built) {
        const gl = V3.gl;
        for (const k of Object.keys(V3.tex))
            gl.deleteTexture(V3.tex[k]);
        V3.tex.top = sideTexture("top");
        V3.tex.bottom = sideTexture("bottom");
    }
    draw3D();
}
let drag3 = null;
glc.addEventListener("mousedown", e => { cancelAnimationFrame(V3.anim); drag3 = { x: e.offsetX, y: e.offsetY, pan: e.shiftKey || e.button === 2, cam: { ...V3.cam } }; glc.style.cursor = "grabbing"; });
glc.addEventListener("contextmenu", e => e.preventDefault());
glc.addEventListener("mousemove", e => {
    if (!drag3)
        return;
    const dx = e.offsetX - drag3.x, dy = e.offsetY - drag3.y, c = V3.cam, c0 = drag3.cam;
    if (drag3.pan) {
        const k = c.dist / H, f = Math.sin(c.pitch);
        c.tx = c0.tx - (-dx * Math.sin(c.yaw) - dy * f * Math.cos(c.yaw)) * k;
        c.ty = c0.ty - (dx * Math.cos(c.yaw) - dy * f * Math.sin(c.yaw)) * k;
        c.tz = c0.tz + dy * Math.cos(c.pitch) * k;
    }
    else {
        c.yaw = c0.yaw - dx * 0.008;
        c.pitch = Math.max(-1.5699, Math.min(1.5699, c0.pitch + dy * 0.008));
    }
    draw3D();
});
window.addEventListener("mouseup", e => {
    if (!drag3)
        return;
    const d = drag3;
    drag3 = null;
    glc.style.cursor = "grab";
    if (e.target !== glc || Math.abs(e.offsetX - d.x) + Math.abs(e.offsetY - d.y) > 3)
        return;
    const i = pick3D(e.offsetX, e.offsetY);
    V3.selBody = i;
    st.selComp = i >= 0 ? S.bodies[i].comp : -1;
    rebuildBodies();
    draw3D();
    if (i < 0) {
        showInfo(null);
        return;
    }
    const bd = S.bodies[i], how = bd.render === "model" ? "model placed as the file places it" : bd.render === "fitted" ? `model fitted to the body's outline (${bd.fit})` : `extruded outline${bd.fit ? ` (${bd.fit})` : ""}`;
    inspect(() => imodel("body", S.comps[bd.comp].ref, [isection("3D body", [irow("Model", bd.model || "extruded"), irow("Placement", how),
            irow("Height", `${fmtLen(bd.zs ? bd.zs[0] : bd.z0)} to ${fmtLen(bd.zs ? bd.zs[1] : bd.z1)} from the ${bd.side} face`)]), boardPart(bd.comp)], { subtitle: "3D body", target: { comp: bd.comp, net: -1 } }));
});
// the body whose box (outline and height) the ray of a pixel meets first
function pick3D(X, Y) {
    const M = inv(mvp()), nx = 2 * X / W - 1, ny = 1 - 2 * Y / H;
    const un = v => { const r = [0, 1, 2, 3].map(i => M[i] * v[0] + M[4 + i] * v[1] + M[8 + i] * v[2] + M[12 + i] * v[3]); return [r[0] / r[3], r[1] / r[3], r[2] / r[3]]; };
    const p0 = un([nx, ny, -1, 1]), p1 = un([nx, ny, 1, 1]), d = [p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]], T = S.board3d.thickness;
    let best = -1, bt = Infinity;
    (S.bodies || []).forEach((bd, i) => {
        let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
        for (let k = 0; k < bd.ring.length; k += 2) {
            const q = P3(bd.ring[k], bd.ring[k + 1], 0);
            x0 = Math.min(x0, q[0]);
            x1 = Math.max(x1, q[0]);
            y0 = Math.min(y0, q[1]);
            y1 = Math.max(y1, q[1]);
        }
        const za = bd.side === "bottom" ? -bd.z1 : T + bd.z0, zb = bd.side === "bottom" ? -bd.z0 : T + bd.z1;
        let t0 = -Infinity, t1 = Infinity;
        for (const [lo, hi, o, dd] of [[x0, x1, p0[0], d[0]], [y0, y1, p0[1], d[1]], [za, zb, p0[2], d[2]]]) {
            if (Math.abs(dd) < 1e-12) {
                if (o < lo || o > hi) {
                    t0 = Infinity;
                    break;
                }
                continue;
            }
            let a = (lo - o) / dd, b2 = (hi - o) / dd;
            if (a > b2)
                [a, b2] = [b2, a];
            t0 = Math.max(t0, a);
            t1 = Math.min(t1, b2);
        }
        if (t0 <= t1 && t1 > 0 && t0 < bt) {
            bt = t0;
            best = i;
        }
    });
    return best;
}
glc.addEventListener("wheel", e => { e.preventDefault(); V3.cam.dist = Math.min(Math.max(V3.cam.dist * Math.exp(e.deltaY * 0.0012), 5), 3000); draw3D(); }, { passive: false });
// ---- board/tabs.ts
// ================================================================== layers: order, current layer, presets
// The layers of a board are listed in the dock's Layers panel (c0301, panels/layers); the bottom bar keeps the
// sheet tabs of a schematic only. buildTabs() keeps its name: it refreshes the panel and the status bar.
const TAB_ORDER = id => {
    const k = id.endsWith(".Cu") ? (id === "F.Cu" ? 0 : id === "B.Cu" ? 2 : 1) : id.startsWith("Mech") ? 3 : id.endsWith("SilkS") ? 4 : id.endsWith("Paste") ? 5 : id.endsWith("Mask") ? 6
        : id.endsWith("CrtYd") ? 7 : id.endsWith("Fab") ? 8 : id === "Edge.Cuts" ? 9 : id.startsWith("View.") ? 11 : 10;
    return k;
};
function tabLayers() { return [...S.layers].sort((a, b) => (a.tab ?? TAB_ORDER(a.id) * 100) - (b.tab ?? TAB_ORDER(b.id) * 100) || (a.id.startsWith("B.") - b.id.startsWith("B.")) || a.id.localeCompare(b.id, undefined, { numeric: true })); }
function buildTabs() {
    buildLayers();
    const cur = S.layers.find(l => l.id === st.cur);
    $("cur").textContent = cur ? `Layer ${cur.name}${st.single ? " · only this layer" : ""}` : "";
}
function setCurrent(id) { st.cur = id; vis.set(id, true); buildTabs(); draw(); }
function stepCurrent(dir) { const L = tabLayers().filter(l => vis.get(l.id)); if (!L.length)
    return; let i = L.findIndex(l => l.id === st.cur); i = (i + dir + L.length) % L.length; setCurrent(L[i].id); }
const SETS = { "All layers": () => true, "Signal layers": l => l.kind === "copper" || VIEWL(l.id), "Top side": l => l.side !== "bottom", "Bottom side": l => l.side !== "top", "Default": l => l.visible };
function applyPreset(name) {
    if (name === "Current layer only")
        st.single = !st.single;
    else {
        st.single = false;
        for (const l of S.layers)
            vis.set(l.id, SETS[name](l));
    }
    buildTabs();
    draw();
}
$("ls").onclick = e => {
    e.stopPropagation();
    const mnu = $("lsmenu");
    mnu.innerHTML = "";
    for (const name of [...Object.keys(SETS), "Current layer only"]) {
        const d = document.createElement("button");
        d.type = "button";
        d.className = "menuItem";
        d.setAttribute("role", "menuitem");
        d.textContent = name;
        if (name === "Current layer only") {
            d.setAttribute("aria-checked", String(st.single));
            d.setAttribute("role", "menuitemcheckbox");
        }
        d.onclick = () => { mnu.style.display = "none"; applyPreset(name); };
        mnu.appendChild(d);
    }
    const r = $("ls").getBoundingClientRect();
    mnu.style.left = `${Math.max(8, r.right - 232)}px`;
    mnu.style.top = `${r.bottom + 6}px`;
    mnu.style.display = mnu.style.display === "block" ? "none" : "block";
};
window.addEventListener("click", () => { $("lsmenu").style.display = "none"; });
// ---- panels/tree.tsx
// ================================================================== project tree (left panel)
// A Preact component (c0300): the project, its groups (each folds) and their documents, the open one marked; a
// document that is missing or has no viewer says so.
const KIND_COLOR = { pcb: "#3fb950", schematic: "#d29922", "schematic-library": "#a371f7", "pcb-library": "#58a6ff", "integrated-library": "#58a6ff", "output-job": "#8b949e", rules: "#8b949e",
    stackup: "#8b949e", project: "#8b949e", "library-table": "#8b949e", draftsman: "#db61a2", other: "#6e7681" };
const TREE_CLOSED = new Set();
function ProjectTree({ project }) {
    return preact.h(preact.Fragment, null,
        preact.h("div", { class: "proj", title: `${project.source} project` },
            preact.h(Icon, { name: "folder" }),
            preact.h("span", null, project.project_file || project.name)),
        project.groups.map(g => {
            const closed = TREE_CLOSED.has(g.name);
            return preact.h("div", { class: "grpBox", key: g.name },
                preact.h("div", { class: "grp" + (closed ? " closed" : ""), role: "button", tabIndex: 0, "aria-expanded": Boolean(!closed), onClick: () => toggleTreeGroup(g.name), onKeyDown: e => { if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        toggleTreeGroup(g.name);
                    } } },
                    preact.h("span", { class: "chev" },
                        preact.h(Icon, { name: "chevRight", size: 12 })),
                    preact.h("span", { class: "grpName" }, g.name),
                    preact.h("span", { class: "grpN" }, g.documents.length)),
                closed ? null : preact.h("div", { class: "grpList" }, g.documents.map(d => preact.h("div", { key: d.id, class: "doc" + (DOC && DOC.id === d.id ? " sel" : "") + (d.present ? "" : " missing") + (d.viewable ? "" : " noview"), role: "button", tabIndex: 0, "aria-current": DOC && DOC.id === d.id ? "true" : undefined, title: `${d.path} · ${d.kind}${d.present ? d.viewable ? "" : " (no viewer yet)" : " (missing)"}`, onClick: () => { openDoc(d); setSidebar(false); }, onKeyDown: e => { if (e.key === "Enter") {
                        openDoc(d);
                        setSidebar(false);
                    } } },
                    preact.h("span", { class: "ic", style: `background:${KIND_COLOR[d.kind] || KIND_COLOR.other}` }),
                    preact.h("span", { class: "docName" }, d.name)))));
        }));
}
function toggleTreeGroup(name) { if (TREE_CLOSED.has(name))
    TREE_CLOSED.delete(name);
else
    TREE_CLOSED.add(name); buildTree(); }
function buildTree() {
    const docs = PROJECT ? PROJECT.groups.reduce((n, g) => n + g.documents.length, 0) : 0;
    showSection("project", true, docs || undefined, "Project");
    preact.render(PROJECT ? preact.h(ProjectTree, { project: PROJECT }) : null, $("tree"));
}
// ---- core/documents.ts
let navigation = 0, loadingNavigation = 0;
function docCard(d, state, error) {
    REVIEW.doc = null;
    buildProjectReview();
    preact.render(null, $("infoEmpty"));
    $("doccard").style.display = "flex";
    $("tablewrap").style.display = "none";
    cv.style.display = "none";
    glc.style.display = "none";
    const kind = state || (!d.present ? "missing" : !d.viewable ? "noviewer" : "empty");
    const project = !allDocs().some(x => x.viewable && x.present);
    preact.render(preact.h(DocCard, { doc: d, state: kind, error, project, onRetry: () => retryDoc(d) }), $("doctext"));
}
function retryDoc(d) {
    if (!DOC || DOC.id !== d.id)
        return;
    invalidateScene(d.id);
    openDoc(d);
}
async function sceneOf(d) {
    if (SCENES.has(d.id))
        return SCENES.get(d.id);
    const read = (SCENE_READS.get(d.id) || 0) + 1;
    SCENE_READS.set(d.id, read);
    if (RAW.has(d.id)) {
        const raw = RAW.get(d.id), sc = toUnits(await unpackScene(raw));
        if (SCENE_READS.get(d.id) === read && RAW.get(d.id) === raw) {
            RAW.delete(d.id);
            SCENES.set(d.id, sc);
        }
        return sc;
    }
    if (!LIVE)
        return null;
    const r = await fetch(`scene/${encodeURIComponent(d.id)}.json`, { cache: "no-store" });
    if (!r.ok)
        throw new Error(await r.text());
    const sc = toUnits(await r.json());
    if (SCENE_READS.get(d.id) === read)
        SCENES.set(d.id, sc);
    return sc;
}
function invalidateScene(id) {
    SCENES.delete(id);
    SCENE_READS.set(id, (SCENE_READS.get(id) || 0) + 1);
}
async function openDoc(d, keepView) {
    // A successful token lets callers verify ownership again after awaiting this function.
    const generation = ++navigation;
    if (!DOC || DOC.id !== d.id) {
        st.version = null;
        if (LIB) {
            setLib(null);
            document.body.classList.remove("lib");
        }
    }
    setDoc(d);
    buildTree();
    showInfo(null);
    if (!keepView)
        setDocTitle(d.name);
    if (!d.viewable || !d.present) {
        docCard(d);
        return 0;
    }
    if (!keepView)
        docCard(d, "reading");
    loadingNavigation = generation;
    setLoading(true);
    let sc;
    try {
        sc = await sceneOf(d);
    }
    catch (e) {
        if (generation === navigation)
            docCard(d, "error", e.message);
        return 0;
    }
    finally {
        if (loadingNavigation === generation) {
            loadingNavigation = 0;
            setLoading(false);
        }
    }
    if (generation !== navigation)
        return 0;
    if (!sc) {
        docCard(d);
        return 0;
    }
    $("doccard").style.display = "none";
    loadScene(sc, keepView);
    return generation;
}
function loadScene(scene, keepView) {
    st.mpts = [];
    st.mhover = null;
    st.lastHit = null;
    st.selFinding = -1;
    $("tablewrap").style.display = "none";
    document.body.classList.remove("table");
    cv.style.display = "block";
    if (scene.kind === "table")
        loadTable(scene);
    else if (scene.kind === "library")
        loadLibrary(scene, keepView);
    else if (scene.kind === "schematic")
        loadSch(scene, keepView);
    else
        loadBoard(scene, keepView);
    runReapply(scene); // c0302: the results of this session's runs
    refreshDock();
    refreshSummary();
    refreshToolbar(); // c0301: the dock's tabs and the document's summary
    if (LIVE && !PREVIEW_MODE && DOC && ACTS.doc !== DOC.id) {
        ACTS.doc = DOC.id;
        actionsLoad();
    } // c0303: what the inspector may offer
    REVIEW.doc = DOC?.id || null;
    buildProjectReview();
}
function allDocs() { return PROJECT ? PROJECT.groups.flatMap(g => g.documents) : []; }
function docByFile(name) { const want = String(name).replace(/\\/g, "/").split("/").pop().toLowerCase(); return allDocs().find(d => d.name.toLowerCase() === want && d.viewable && d.present); }
// ---- panels/findings.tsx
// ================================================================== scene, overlays and notes
// findings by group (change c0193): the box draws or hides a group, the title opens its items, the tooltip says the rule;
// a Preact component (change c0304)
function showGroup(id, on) { if (on)
    st.ovOff.delete(id);
else
    st.ovOff.add(id); draw(); }
function openGroup(id) { if (st.ovOpen.has(id))
    st.ovOpen.delete(id);
else
    st.ovOpen.add(id); buildFindings(); }
// keys: a row is never reused for a row of another kind, so no attribute of one is left on the other
function GroupRow({ g, idx }) {
    return preact.h("div", { class: "fg" + (idx.length ? "" : " zero"), title: g.note || "" },
        preact.h("input", { type: "checkbox", checked: !st.ovOff.has(g.id), "aria-label": `Draw ${g.title}`, onChange: e => showGroup(g.id, e.target.checked) }),
        preact.h("span", { class: "sw", style: `background:${g.color}` }),
        preact.h("span", { class: "ft", role: "button", tabIndex: 0, "aria-expanded": Boolean(st.ovOpen.has(g.id)), onClick: () => openGroup(g.id), onKeyDown: e => { if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                openGroup(g.id);
            } } }, g.title),
        preact.h("span", { class: "fn" }, idx.length));
}
function FindingsPanel({ groups, byG }) {
    const out = [], zero = groups.filter(g => !(byG.get(g.id) || []).length);
    const rows = (g, idx) => {
        out.push(preact.h(GroupRow, { key: "g:" + g.id, g: g, idx: idx }));
        if (!st.ovOpen.has(g.id))
            return;
        if (g.note)
            out.push(preact.h("div", { key: "n:" + g.id, class: "fnote" }, g.note));
        for (const i of idx)
            out.push(preact.h("div", { key: "o:" + i, class: "ov" + (i === st.selOv ? " sel" : ""), onClick: () => gotoFinding(i) }, S.overlays[i].label));
    };
    for (const g of groups) {
        const idx = byG.get(g.id) || [];
        if (idx.length)
            rows(g, idx);
    }
    if (zero.length) { // c0300: the groups with no finding fold into one line; each stays a result, one click away
        out.push(preact.h("button", { key: "zero", id: "ovZero", type: "button", class: "zeroLine", "aria-expanded": Boolean(!!st.ovZeroOpen), onClick: () => { st.ovZeroOpen = !st.ovZeroOpen; buildFindings(); } },
            preact.h("span", { class: "chev" },
                preact.h(Icon, { name: "chevRight", size: 12 })),
            `${zero.length} group${zero.length === 1 ? "" : "s"} with no findings`));
        if (st.ovZeroOpen)
            for (const g of zero)
                rows(g, []);
    }
    if (!groups.length)
        out.push(preact.h(Empty, { key: "empty", text: "No finding groups for this board." }));
    return preact.h(preact.Fragment, null, out);
}
function buildFindings() {
    const groups = [...(S.meta.findings || [])], byG = new Map();
    (S.overlays || []).forEach((o, i) => { const g = ovGroup(o); if (!byG.has(g))
        byG.set(g, []); byG.get(g).push(i); });
    for (const g of byG.keys())
        if (!groups.some(x => x.id === g))
            groups.push({ id: g, title: g, color: S.overlays[byG.get(g)[0]].color, n: byG.get(g).length, note: "" });
    const total = (S.overlays || []).length;
    showSection("findings", groups.length > 0, total, "Findings", total ? "warn" : "");
    preact.render(preact.h(FindingsPanel, { groups: groups, byG: byG }), $("overlays"));
}
function clearFindings() { showSection("findings", false); preact.render(null, $("overlays")); } // a sheet: no finding group
function gotoFinding(i) {
    const o = S.overlays[i];
    if (st.mode3d)
        set3D(false);
    st.selOv = i;
    st.selNet = -1;
    st.selComp = -1;
    st.ovOff.delete(ovGroup(o));
    const xs = o.pts.map(p => p[0]), ys = o.pts.map(p => p[1]);
    const b = o.bbox ? [Math.min(o.bbox[0], ...xs), Math.min(o.bbox[1], ...ys), Math.max(o.bbox[2], ...xs), Math.max(o.bbox[3], ...ys)] : [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
    if (o.layer && (o.layer.startsWith("B.") !== view.mirror))
        flip();
    const g = (S.meta.findings || []).find(x => x.id === ovGroup(o));
    fit([b[0] - 4, b[1] - 4, b[2] + 4, b[3] + 4]);
    buildFindings();
    inspect(() => imodel("finding", g ? g.title : ovGroup(o), [isection("Finding", [irow("Group", g ? g.title : ovGroup(o)), irow("Item", o.label),
            irow("Layer", o.layer), irow("Rule", g && g.note)])], { subtitle: "Review finding", target: { overlay: i, comp: -1, net: -1 } }));
}
// ---- panels/roles.tsx
// ================================================================== the Net roles panel (c0305)
// A side bar section of a board with role data (scene.roles): the legend of the role kinds (colour, glyph,
// name and count; a click lists one kind only), the role of each net (glyph, net, kind and current,
// confidence, state), the groups (hot loops, gate loops, Kelvin pairs) and the role findings by code. A net row
// highlights its net, a group row frames its pads, a finding row selects its marker; each opens in the
// inspector. In a served page the foot runs `fenolite roles --check` again and, with --allow-actions, plans
// Confirm roles for the inferred rows. The Roles group of the Layers panel (RoleLayers) shows or hides the
// overlays of roles/draw. Ported from the Net Roles workspace of c0245-engineering-viewer into c0301's look.
function ink(hex) { const n = parseInt(String(hex).slice(1, 7), 16); const l = (0.2126 * (n >> 16) + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255)) / 255; return l > 0.55 ? "#111317" : "#ffffff"; }
function RoleChip({ kind }) {
    const c = roleColor(kind);
    return preact.h("span", { class: "rchip", style: `background:${c};color:${ink(c)}`, title: roleName(kind), "aria-hidden": "true" }, ROLE_GLYPH[kind] || "?");
}
function frame(pts, margin) {
    if (!pts.length)
        return;
    const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
    fit([Math.min(...xs) - margin, Math.min(...ys) - margin, Math.max(...xs) + margin, Math.max(...ys) + margin]);
}
function selectRoleGroup(i) {
    const g = rolesData().groups[i];
    if (st.mode3d)
        set3D(false);
    ROLE_SEL.group = i;
    ROLE_SEL.finding = -1;
    st.selNet = -1;
    st.selComp = -1;
    frame(g.points || [], 3);
    inspect(() => groupModel(i));
    buildRoles();
    draw();
}
function selectRoleFinding(i) {
    const x = rolesData().findings[i];
    if (st.mode3d)
        set3D(false);
    ROLE_SEL.finding = i;
    ROLE_SEL.group = -1;
    if (x.at) {
        const b = x.box || [x.at[0], x.at[1], x.at[0], x.at[1]], m = Math.max(b[2] - b[0], b[3] - b[1], 6) * 0.8;
        fit([b[0] - m, b[1] - m, b[2] + m, b[3] + m]);
    }
    inspect(() => roleFindingModel(i));
    buildRoles();
    draw();
}
function rolesRunOffered() { return !!(RUNS.enabled && RUNS.offer?.commands?.roles && DOC && rolesBoard()); }
function confirmOffered() { const A = window.FenoliteActions && window.FenoliteActions.state; return !!(A && A.enabled && A.offer?.roles?.available); }
function confirmRoles(nets, groups) { window.FenoliteActions.plan("roles", { nets, groups }); }
const rolesBoard = () => !!S && !S.kind && !!S.prims;
function Legend({ R }) {
    return preact.h("div", { class: "rlegend", role: "group", "aria-label": "Role kinds" }, roleLegend(R).map(k => preact.h("button", { type: "button", class: "rleg" + (ROLE_SEL.kind === k.kind ? " on" : ""), "aria-pressed": ROLE_SEL.kind === k.kind, "data-kind": k.kind, "data-tip": ROLE_SEL.kind === k.kind ? "List every kind" : `List the ${k.name} nets only`, onClick: () => { ROLE_SEL.kind = ROLE_SEL.kind === k.kind ? "" : k.kind; buildRoles(); } },
        preact.h(RoleChip, { kind: k.kind }),
        preact.h("span", { class: "rlegName" }, k.name),
        preact.h("span", { class: "rlegN" }, k.n))));
}
function NetRows({ R }) {
    const rows = R.roles.filter(r => !ROLE_SEL.kind || r.kind === ROLE_SEL.kind)
        .sort((a, b) => ROLE_ORDER.indexOf(a.kind) - ROLE_ORDER.indexOf(b.kind) || natural(a.net, b.net));
    if (!rows.length)
        return preact.h(Empty, { text: "No role on this board." });
    return preact.h("div", { class: "list rlist", id: "roleNets" }, rows.map(r => preact.h("div", { key: r.net, class: "navi rrow" + (r.net_index >= 0 && r.net_index === st.selNet ? " sel" : ""), "data-net": r.net, title: `${r.net}: ${roleName(r.kind)}, ${r.state}${r.rule ? ` (rule ${r.rule})` : ""}`, onClick: () => { if (r.net_index >= 0) {
            ROLE_SEL.group = -1;
            ROLE_SEL.finding = -1;
            selectNetAt(r.net_index);
            buildRoles();
        } } },
        preact.h(RoleChip, { kind: r.kind }),
        preact.h("span", { class: "rnet" }, r.net),
        preact.h("span", { class: "rkind" },
            roleName(r.kind),
            r.milliamps != null ? preact.h("small", null, amps(r.milliamps)) : null),
        preact.h("span", { class: "rconf c-" + (r.confidence || r.state) }, r.confidence || r.state),
        preact.h("span", { class: "rstate s-" + r.state, "aria-label": r.state }, STATE_MARK[r.state] || ""))));
}
function GroupRows({ R }) {
    if (!R.groups.length)
        return null;
    return preact.h(preact.Fragment, null,
        preact.h("div", { class: "navg" }, "Groups"),
        preact.h("div", { class: "list rlist", id: "roleGroups" }, R.groups.map((g, i) => preact.h("div", { key: g.name, class: "navi rrow" + (i === ROLE_SEL.group ? " sel" : ""), "data-group": g.name, title: `${GROUP_LABEL[g.type]}: ${g.pads.join(", ")}`, onClick: () => selectRoleGroup(i) },
            preact.h(RoleChip, { kind: GROUP_KIND[g.type] }),
            preact.h("span", { class: "rnet" }, g.name),
            preact.h("span", { class: "rkind" }, (GROUP_LABEL[g.type] || g.type).toLowerCase()),
            preact.h("span", { class: "rconf c-" + (g.confidence || g.origin) }, g.confidence || g.origin),
            preact.h("span", { class: "rstate s-" + g.origin, "aria-label": g.origin }, STATE_MARK[g.origin] || "")))));
}
function FindingRows({ R }) {
    if (!R.findings.length)
        return null;
    const by = new Map();
    R.findings.forEach((x, i) => { if (!by.has(x.code))
        by.set(x.code, []); by.get(x.code).push(i); });
    const out = [preact.h("div", { key: "h", class: "navg" }, "Role findings")];
    for (const [code, list] of by) {
        out.push(preact.h("div", { key: "c:" + code, class: "rcode" },
            preact.h("span", { class: "sw", style: `background:${SEV_COLOR[R.findings[list[0]].severity] || "#888888"}` }),
            ` ${code} (${list.length})`));
        for (const i of list) {
            const x = R.findings[i];
            out.push(preact.h("div", { key: "f:" + i, class: "navi rfind" + (i === ROLE_SEL.finding ? " sel" : ""), "data-code": x.code, title: String(x.where), onClick: () => selectRoleFinding(i) },
                String(x.message),
                x.at ? null : preact.h("small", null, "(no position)")));
        }
    }
    return preact.h("div", { class: "list", id: "roleFindings" }, out);
}
function Foot({ R }) {
    const nets = inferredRoles(), groups = inferredGroups(), run = rolesRunOffered(), confirm = confirmOffered() && (nets.length + groups.length) > 0;
    const busy = !!RUNS.job || !!window.FenoliteActions?.state?.job;
    return preact.h("div", { class: "rfoot" },
        run ? preact.h("button", { type: "button", id: "rolesRun", class: "tb small", disabled: busy, onClick: () => window.FenoliteRuns.start("roles", {}) },
            preact.h(Icon, { name: "refresh", size: 14 }),
            preact.h("span", { class: "lbl" }, "Run roles again")) : null,
        confirm ? preact.h("button", { type: "button", id: "rolesConfirm", class: "tb small accentBtn", disabled: busy, "data-tip": "Plan fenolite roles --accept for every inferred role and group", onClick: () => confirmRoles(nets, groups) },
            preact.h(Icon, { name: "check", size: 14 }),
            preact.h("span", { class: "lbl" }, `Confirm ${nets.length + groups.length} inferred…`)) : null,
        !run && !confirm && nets.length + groups.length ? preact.h("p", { class: "hint" }, `Confirm with fenolite roles ${R.document || "BOARD"} --accept NET, or serve the page with --allow-actions.`) : null);
}
function RolesPanel({ R }) {
    const n = R.counts.roles;
    return preact.h(preact.Fragment, null,
        preact.h("p", { class: "rsum", id: "roleSummary" },
            `${n.declared} declared · ${n.confirmed} confirmed · ${n.inferred} inferred`,
            preact.h("span", { class: "rev" }, R.evidence.level)),
        (R.notes || []).map((t, k) => preact.h("div", { key: "n" + k, class: "notes" }, t)),
        preact.h(Legend, { R: R }),
        preact.h(NetRows, { R: R }),
        preact.h(GroupRows, { R: R }),
        preact.h(FindingRows, { R: R }),
        preact.h(Foot, { R: R }));
}
function buildRoles() {
    const box = $("roleList");
    if (!box)
        return;
    const R = rolesData();
    if (!R && rolesRunOffered()) { // a served board without role data yet: the run that gives it
        showSection("roles", true, "", "Net roles");
        preact.render(preact.h(preact.Fragment, null,
            preact.h(Empty, { text: "No role data for this board yet." }),
            preact.h("div", { class: "rfoot" },
                preact.h("button", { type: "button", id: "rolesRun", class: "tb small", disabled: !!RUNS.job, onClick: () => window.FenoliteRuns.start("roles", {}) },
                    preact.h(Icon, { name: "play", size: 14 }),
                    preact.h("span", { class: "lbl" }, "Run fenolite roles --check")))), box);
        return;
    }
    if (!R) {
        showSection("roles", false);
        preact.render(null, box);
        return;
    }
    const f = R.counts.findings;
    showSection("roles", true, R.roles.length, "Net roles", f.error ? "err" : f.warning ? "warn" : "");
    preact.render(preact.h(RolesPanel, { R: R }), box);
}
// ---- the Roles group of the Layers panel
const OVERLAYS = [["colors", "Role colours", "power"], ["loops", "Loops (hot and gate)", "switch_node"], ["kelvin", "Kelvin pairs", "kelvin"], ["findings", "Role findings", ""]];
function setRoleView(key, on) { ROLE_VIEW[key] = on; keepRoleView(); draw(); buildLayers(); }
function RoleLayers() {
    if (!rolesData())
        return null;
    const shown = OVERLAYS.filter(([k]) => ROLE_VIEW[k]).length;
    return preact.h("section", { class: "lgroup", "aria-label": "Roles", id: "roleLayers" },
        preact.h("div", { class: "lgHead" },
            preact.h("span", { class: "lgTitle" }, "Roles"),
            preact.h("span", { class: "lgN" }, `${shown}/${OVERLAYS.length}`)),
        OVERLAYS.map(([k, title, kind]) => {
            const on = !!ROLE_VIEW[k];
            return preact.h("div", { key: k, class: "lrow rlrow" + (on ? "" : " off"), "data-overlay": k },
                preact.h("span", null),
                preact.h("span", { class: "sw", style: `background:${kind ? roleColor(kind) : SEV_COLOR.warning}` }),
                preact.h("span", { class: "lname", onClick: () => setRoleView(k, !on) }, title),
                preact.h("span", null),
                preact.h("button", { type: "button", class: "tb icon small ghost leye", "aria-pressed": on, "aria-label": `${on ? "Hide" : "Show"} ${title.toLowerCase()}`, "data-tip": on ? "Hide" : "Show", onClick: () => setRoleView(k, !on) },
                    preact.h(Icon, { name: on ? "eye" : "eyeOff", size: 14 })));
        }));
}
// ---- board/load.ts
function buildPanels() {
    buildFindings();
    const c = S.meta.counts || {};
    $("notes").innerHTML = (S.meta.notes || []).map(esc).join("<br>") + `${(S.meta.notes || []).length ? "<br>" : ""}Read by the ${esc(S.meta.backend || "?")} backend, evidence ${esc(S.meta.evidence || "?")}.` +
        `<br>${c.footprints || 0} parts · ${c.pads || 0} pads · ${c.tracks || 0} tracks · ${c.vias || 0} vias · ${c.zones || 0} zones`;
}
function loadBoard(scene, keepView) {
    document.body.classList.remove("sch");
    st.itemInfo = false;
    const first = S === null || S !== scene && !keepView;
    if (S !== scene) {
        ROLE_SEL.group = -1;
        ROLE_SEL.finding = -1;
    }
    setS(scene);
    for (const l of S.layers)
        if (!vis.has(l.id))
            vis.set(l.id, l.visible);
    if (!st.cur || !S.layers.some(l => l.id === st.cur))
        st.cur = (S.layers.find(l => l.id === "F.Cu") || S.layers[0] || {}).id;
    if (st.query)
        st.query = st.query.text && S.prims ? { text: st.query.text, ...queryRun(S, queryParse(st.query.text)) } : null;
    buildCaches();
    resetRoleCache();
    buildTabs();
    buildPanels();
    buildRoles();
    buildDiffList();
    buildMessages();
    buildVariants();
    buildReview();
    applyProjNet();
    cv.style.display = st.mode3d ? "none" : "block";
    setDocTitle(S.meta.name);
    if (V3.built) {
        V3.built = false;
        if (st.mode3d) {
            build3D();
            draw3D();
        }
    }
    if (first) {
        setFitted(false);
        fit();
    }
    else
        draw();
}
// ---- panels/review.tsx
// ================================================================== review panels (c0187): filter, highlight, components, nets
const HL_ALPHA = { dim: 0.22, mask: 0.06, normal: 1 }; // c0301: Dim at 0.22
const ROW = 24;
function vlist(box, items, row, click, selected, empty) {
    box.style.height = items.length ? `${Math.min(240, items.length * ROW + 4)}px` : "auto";
    if (!items.length) {
        box.onscroll = null;
        preact.render(preact.h(Empty, { text: empty || "Nothing to list." }), box);
        return;
    }
    const paint = () => {
        const top = box.scrollTop, h = box.clientHeight || 240;
        const a = Math.max(0, Math.floor(top / ROW) - 4), z = Math.min(items.length, Math.ceil((top + h) / ROW) + 4), rows = [];
        for (let i = a; i < z; i++)
            rows.push(preact.h("div", { key: i, class: "navi vrow" + (selected(items[i]) ? " sel" : ""), style: `top:${i * ROW}px;height:${ROW}px;line-height:${ROW}px`, onClick: () => click(items[i]) }, row(items[i])));
        preact.render(preact.h("div", { class: "vinner", style: `height:${items.length * ROW}px` }, rows), box);
    };
    box.onscroll = paint;
    paint();
}
function netBounds(ni) {
    let b = null;
    for (const list of byLayer.values())
        for (const [pr, q] of list)
            if (pr[3] === ni)
                b = b ? [Math.min(b[0], q[0]), Math.min(b[1], q[1]), Math.max(b[2], q[2]), Math.max(b[3], q[3])] : [...q];
    return b;
}
function primBounds(set) {
    let b = null;
    for (const list of byLayer.values())
        for (const [pr, q] of list)
            if (set.has(pr))
                b = b ? [Math.min(b[0], q[0]), Math.min(b[1], q[1]), Math.max(b[2], q[2]), Math.max(b[3], q[3])] : [...q];
    return b;
}
function selectCompAt(ci) { if (st.mode3d)
    set3D(false); st.selComp = ci; st.selNet = -1; const b = S.comps[ci].bbox; if (b)
    fit([b[0] - 5, b[1] - 5, b[2] + 5, b[3] + 5]); inspect(() => partModel(ci)); buildReview(); draw(); }
function selectNetAt(ni) {
    if (st.mode3d)
        set3D(false);
    st.selNet = ni;
    st.selComp = -1;
    shareNet(S.nets[ni]);
    const b = netBounds(ni);
    if (b)
        fit([b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3]);
    inspect(() => netModel(ni));
    buildReview();
    draw();
}
const COMP_SORT = { ref: c => c.ref, value: c => String(c.value || ""), footprint: c => String(c.footprint || "") };
function buildReview() {
    if (!S || S.kind || !S.prims)
        return;
    const qy = st.query, inQ = qy ? new Set(qy.comps) : null;
    const cfRaw = $("compFilter").value.trim(), nfRaw = $("netFilter").value.trim(), cf = cfRaw.toLowerCase(), nf = nfRaw.toLowerCase();
    const key = COMP_SORT[$("compSort").value] || COMP_SORT.ref;
    const comps = S.comps.map((c, i) => i).filter(i => !inQ || inQ.has(i)).filter(i => { const c = S.comps[i]; return !cf || [c.ref, c.value, c.footprint].some(v => String(v || "").toLowerCase().includes(cf)); })
        .sort((a, b) => natural(key(S.comps[a]), key(S.comps[b])) || natural(S.comps[a].ref, S.comps[b].ref));
    let netSet = null;
    if (qy) {
        netSet = new Set();
        for (const pr of qy.prims)
            if (pr[3] >= 0)
                netSet.add(pr[3]);
    }
    const info = i => (S.netinfo || [])[i] || { pads: 0, length: 0 }, ns = $("netSort").value;
    const nets = S.nets.map((n, i) => i).filter(i => S.nets[i] && (!netSet || netSet.has(i)) && (!nf || S.nets[i].toLowerCase().includes(nf)))
        .sort((a, b) => (ns === "pads" ? info(b).pads - info(a).pads : ns === "length" ? info(b).length - info(a).length : 0) || natural(S.nets[a], S.nets[b]));
    const total = S.nets.filter(Boolean).length;
    showSection("components", true, comps.length === S.comps.length ? comps.length : `${comps.length} / ${S.comps.length}`, "Components");
    showSection("nets", true, nets.length === total ? nets.length : `${nets.length} / ${total}`, "Nets");
    const why = (raw, none, what) => raw ? `No ${what} match “${raw}”.` : qy ? `No ${what} in the filter’s result.` : none;
    vlist($("compList"), comps, i => { const c = S.comps[i]; return preact.h(preact.Fragment, null,
        preact.h("b", null, c.ref),
        preact.h("small", null, [c.value, c.footprint, c.side === "bottom" ? "bottom" : ""].filter(Boolean).join(" · "))); }, selectCompAt, i => i === st.selComp, why(cfRaw, "No components on this board.", "components"));
    vlist($("netList"), nets, i => { const n = (S.netinfo || [])[i]; return preact.h(preact.Fragment, null,
        preact.h("b", null, S.nets[i]),
        n ? preact.h("small", null, `${n.pads} pads · ${fmtLen(n.length * MM)}`) : null); }, selectNetAt, i => i === st.selNet, why(nfRaw, "No nets on this board.", "nets"));
    $("queryInfo").textContent = qy ? (qy.prims.size || qy.comps.length ? `${qy.comps.length} part(s) · ${qy.prims.size} primitive(s)` : "Nothing matches the filter.") : "";
}
function applyQuery(text, zoom) {
    if (!S || S.kind || !S.prims)
        return;
    text = text.trim();
    if (!text) {
        clearQuery();
        return;
    }
    st.query = { text, ...queryRun(S, queryParse(text)) };
    qCache.delete(text);
    buildReview();
    if (zoom && st.query.prims.size) {
        const b = primBounds(st.query.prims);
        if (b)
            fit([b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3]);
    }
    draw();
}
function clearQuery() { st.query = null; $("query").value = ""; st.selNet = -1; st.selComp = -1; showInfo(null); buildReview(); draw(); }
let qTimer = null;
$("query").addEventListener("input", e => { clearTimeout(qTimer); qTimer = setTimeout(() => applyQuery(e.target.value, false), 250); });
$("query").addEventListener("keydown", e => { if (e.key === "Enter") {
    clearTimeout(qTimer);
    applyQuery(e.target.value, true);
}
else if (e.key === "Escape")
    e.target.blur(); });
$("compFilter").addEventListener("input", buildReview);
$("netFilter").addEventListener("input", buildReview);
$("compSort").addEventListener("change", buildReview);
$("netSort").addEventListener("change", buildReview);
preact.render(preact.h(Icon, { name: "x" }), $("bQClear"));
function findSimilar() {
    if (!S || S.kind)
        return;
    const h = st.lastHit, ci = st.selComp >= 0 ? st.selComp : -1;
    const text = similarQuery(S, h ? h.pr : null, ci >= 0 ? ci : h && h.pr[4] >= 0 && h.pr[3] < 0 ? h.pr[4] : -1);
    if (!text) {
        $("queryInfo").textContent = "Select a part or a primitive first.";
        return;
    }
    $("query").value = text;
    applyQuery(text, false);
}
$("bSimilar").onclick = findSimilar;
$("bQClear").onclick = clearQuery;
$("hlMode").value = HL_ALPHA[st.hl] !== undefined ? st.hl : "dim";
$("hlMode").onchange = e => { st.hl = e.target.value; try {
    localStorage.setItem("fenolite.view.highlight", st.hl);
}
catch (err) { /* private window */ } draw(); };
// ---- measure/edge-tool.ts
// ================================================================== review tools (c0189): edge measure, links, marks, SVG, print
const EDGE_C = "#00d0ff";
function toggleEdge() { st.edge = !st.edge; st.epick = []; st.eres = null; refreshToolbar(); draw(); }
function edgeGroup(h) {
    const pr = h.pr;
    if (!pr[5])
        return [pr];
    return (byLayer.get(h.layer.id) || []).map(e => e[0]).filter(q => q[5] === pr[5] && q[4] === pr[4] && q[1] !== "t");
}
function edgeClick(X, Y) {
    const h = pick(X, Y);
    if (!h)
        return;
    if (st.epick.length >= 2) {
        st.epick = [];
        st.eres = null;
    }
    st.epick.push({ name: h.pr[5] || h.layer.name, layer: h.layer, prims: edgeGroup(h) });
    if (st.epick.length === 2) {
        const [a, b] = st.epick;
        st.eres = edgeBetween(a.prims, b.prims);
        if (st.eres) {
            const d = st.eres.d;
            inspect(() => imodel("measure", `Edge gap ${fmtLen(d)}`, [isection("Edge gap", [irow("Distance", fmtLen(d)), irow("From", `${a.name} · ${a.layer.name}`), irow("To", `${b.name} · ${b.layer.name}`)])], { note: a.layer.id !== b.layer.id ? "Two layers: the distance is measured in the plane." : "" }));
        }
    }
    draw();
}
function drawEdge() {
    if (!st.edge && !st.eres)
        return;
    worldTf();
    ctx.globalAlpha = 0.9;
    for (const g of st.epick) {
        const c = newCache();
        for (const pr of g.prims)
            addPrim(c, pr);
        paintCache(ctx, c, g.layer.id, EDGE_C, 0.55, view.s);
    }
    const r = st.eres;
    if (!r)
        return;
    ctx.globalAlpha = 1;
    ctx.strokeStyle = ctx.fillStyle = EDGE_C;
    ctx.lineWidth = 1.5 / view.s;
    ctx.beginPath();
    ctx.moveTo(r.a[0], r.a[1]);
    ctx.lineTo(r.b[0], r.b[1]);
    ctx.stroke();
    for (const q of [r.a, r.b]) {
        ctx.beginPath();
        ctx.arc(q[0], q[1], 3 / view.s, 0, 2 * Math.PI);
        ctx.fill();
    }
    const txt = `edge ${fmtLen(r.d)}`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const P = w2s(r.b[0], r.b[1]);
    ctx.font = "600 13px system-ui";
    const w = ctx.measureText(txt).width;
    ctx.fillStyle = "#000c";
    ctx.fillRect(P[0] + 8, P[1] + 6, w + 12, 20);
    ctx.fillStyle = EDGE_C;
    ctx.fillText(txt, P[0] + 14, P[1] + 21);
    worldTf();
    $("coord").textContent = `measure: ${txt}`;
}
// ---- core/links.ts
// ---- deep links: the URL's hash keeps the document, the selection, the view, the unit and the layer
function selName() {
    if (!S)
        return "";
    if (isSch())
        return SCH.selComp >= 0 ? S.comps[SCH.selComp].ref : SCH.selNet >= 0 ? "net:" + S.nets[SCH.selNet].name : "";
    return st.selComp >= 0 ? S.comps[st.selComp].ref : st.selNet >= 0 ? "net:" + S.nets[st.selNet] : "";
}
function linkHash() {
    if (!DOC)
        return "";
    const q = new URLSearchParams({ doc: DOC.id });
    const sel = selName();
    if (sel)
        q.set("sel", sel);
    if (PREVIEW_MODE) {
        q.set("preview", "1");
        if (LIB && LIBSEL >= 0)
            q.set("item", LIB.items[LIBSEL].name);
    }
    q.set("z", view.s.toFixed(3));
    q.set("c", `${view.cx.toFixed(4)},${view.cy.toFixed(4)}`);
    q.set("u", UNIT);
    if (!isSch() && st.cur)
        q.set("l", st.cur);
    return q.toString();
}
let linkTimer = null, linkReady = false;
function setLinkReady(v) { linkReady = v; }
function linkLater() { if (!linkReady)
    return; clearTimeout(linkTimer); linkTimer = setTimeout(() => { const h = linkHash(); if (h && location.hash.slice(1) !== h)
    try {
        history.replaceState(null, "", "#" + h);
    }
    catch (e) { /* a sandboxed frame */ } }, 400); }
function applySelect(name) { if (!name || !S)
    return; const n = name.startsWith("net:") ? name.slice(4) : name; find(n); }
function applyLink(q) {
    if (q.get("u") === "mil" || q.get("u") === "mm")
        setUnit(q.get("u"));
    if (q.get("l") && S && S.layers && S.layers.some(l => l.id === q.get("l"))) {
        st.cur = q.get("l");
        vis.set(st.cur, true);
        buildTabs();
    }
    if (q.get("sel"))
        applySelect(q.get("sel"));
    const z = parseFloat(q.get("z")), c = (q.get("c") || "").split(",").map(Number);
    if (z > 0 && c.length === 2 && c.every(Number.isFinite)) {
        view.s = z;
        view.cx = c[0];
        view.cy = c[1];
        setFitted(true);
    }
    draw();
}
async function copyLink() {
    const h = linkHash();
    try {
        history.replaceState(null, "", "#" + h);
    }
    catch (e) { /* ignore */ }
    if (!await copyAndSay(location.href, "Link to this view copied"))
        window.prompt("Link to this view", location.href);
}
// ---- panels/marks.tsx
// ---- review marks: kept by the server in the --marks file, else in this browser until downloaded
let MARKS = [];
const marksKey = () => "fenolite.view.marks:" + (PROJECT ? PROJECT.name : "");
const serverMarks = () => LIVE && PROJECT && PROJECT.marks_file;
function loadMarks(given) {
    MARKS = Array.isArray(given) ? given : [];
    if (!serverMarks())
        try {
            const kept = JSON.parse(localStorage.getItem(marksKey()) || "null");
            if (Array.isArray(kept)) {
                const ids = new Set(MARKS.map(m => m.id));
                MARKS = MARKS.concat(kept.filter(m => !ids.has(m.id)));
            }
        }
        catch (e) { /* no storage */ }
}
async function sendMark(body) {
    if (serverMarks()) {
        const r = await fetch("marks", { method: "POST", headers: { "Content-Type": "application/json", "X-Fenolite-Review": "1" }, body: JSON.stringify(body) });
        const reply = await r.json();
        if (!r.ok) {
            showInfo(`Mark not saved: ${esc(reply.error || r.status)}`);
            return;
        }
        MARKS = reply.marks;
    }
    else {
        MARKS = MARKS.filter(m => m.id !== body.id);
        if (body.note !== null)
            MARKS.push(body);
        try {
            localStorage.setItem(marksKey(), JSON.stringify(MARKS));
        }
        catch (e) { /* no storage */ }
    }
    buildMarks();
    draw();
}
function markClick(x, y) {
    const note = window.prompt("Note for this mark", "");
    if (note === null)
        return;
    sendMark({ id: "m" + Date.now().toString(36), doc: DOC.name, x_nm: Math.round(x * 1e6), y_nm: Math.round(y * 1e6), note, select: selName(), created: new Date().toISOString() });
}
function drawMarks() {
    if (!DOC || !MARKS.length)
        return;
    if (!isSch())
        worldTf();
    ctx.globalAlpha = 1;
    MARKS.forEach((m, i) => {
        if (m.doc !== DOC.name)
            return;
        const x = m.x_nm / 1e6, y = m.y_nm / 1e6, r = 7 / view.s;
        ctx.fillStyle = "#ffd400";
        ctx.strokeStyle = "#000";
        ctx.lineWidth = 1 / view.s;
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x - r * 0.8, y - r * 1.6);
        ctx.arc(x, y - r * 2, r, Math.PI * 0.8, Math.PI * 0.2);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = "#000";
        ctx.font = `600 ${(10 / view.s).toFixed(4)}px system-ui`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(String(i + 1), x, y - r * 2);
        ctx.textAlign = "start";
        ctx.textBaseline = "alphabetic";
    });
}
async function openMark(m, i) {
    const doc = allDocs().find(x => x.name === m.doc);
    if (doc && doc !== DOC) {
        const shown = await openDoc(doc);
        if (!shown || shown !== navigation)
            return;
    }
    if (st.mode3d)
        set3D(false);
    const x = m.x_nm / 1e6, y = m.y_nm / 1e6, e = isSch() ? 25 : 5;
    fit([x - e, y - e, x + e, y + e]);
    inspect(() => imodel("mark", `Mark ${i + 1}`, [isection("Review mark", [irow("Note", m.note || "(no note)"), irow("On", m.select), irow("Document", m.doc), irow("Created", m.created)])], { subtitle: serverMarks() ? "Kept in the marks file" : "Kept in this browser" }));
}
// A row keeps its click as the element's onclick (c0300): the navigation tests call it and await its promise.
function MarksPanel({ marks }) {
    return preact.h(preact.Fragment, null,
        marks.length ? marks.map((m, i) => preact.h("div", { key: m.id, class: "navi mark", ref: el => { if (el)
                el.onclick = () => openMark(m, i); } },
            preact.h("span", { class: "markNo" }, i + 1),
            preact.h("span", { class: "markText" },
                m.note || "(no note)",
                preact.h("small", null, `${m.doc}${m.select ? " · " + m.select : ""}`)),
            preact.h("button", { type: "button", class: "tb icon ghost small", "aria-label": `Delete mark ${i + 1}`, "data-tip": "Delete this mark", onClick: ev => { ev.stopPropagation(); if (window.confirm(`Delete mark ${i + 1}?`))
                    sendMark({ id: m.id, note: null }); } },
                preact.h(Icon, { name: "x" })))) : preact.h(Empty, { text: "No marks yet. Press N, then click the drawing to drop one.", icon: "pin" }),
        !serverMarks() ? preact.h("button", { type: "button", class: "tb wide", "data-tip": "Save them as a fenolite.review.v0 file for fenolite view --marks", onClick: () => download(JSON.stringify({ schema: "fenolite.review.v0", marks: MARKS }, null, 2) + "\n", "review.json", "application/json") },
            preact.h(Icon, { name: "download" }),
            preact.h("span", { class: "lbl" }, "Download marks")) : null);
}
function buildMarks() {
    showSection("marks", MARKS.length > 0 || !LIVE, MARKS.length, "Marks" + (serverMarks() ? "" : " · in this browser"));
    preact.render(preact.h(MarksPanel, { marks: MARKS }), $("marksList"));
}
// ---- export/svg.ts
// ---- SVG: the view drawn again into a recorder of the canvas calls the page makes, as vector paths
class RecPath {
    constructor() { this.c = []; }
    moveTo(x, y) { this.c.push(["M", x, y]); }
    lineTo(x, y) { this.c.push(["L", x, y]); }
    closePath() { this.c.push(["Z"]); }
    rect(x, y, w, h) { this.c.push(["M", x, y], ["L", x + w, y], ["L", x + w, y + h], ["L", x, y + h], ["Z"]); }
    arc(cx, cy, r, a0, a1, ccw) { this.ellipse(cx, cy, r, r, 0, a0, a1, ccw); }
    ellipse(cx, cy, rx, ry, rot, a0, a1, ccw) {
        const T = 2 * Math.PI;
        let span = ccw ? a0 - a1 : a1 - a0;
        if (Math.abs(span) >= T)
            span = T;
        else
            span = ((span % T) + T) % T;
        const n = Math.max(8, Math.ceil(span / (Math.PI / 32))), cr = Math.cos(rot), sr = Math.sin(rot);
        for (let i = 0; i <= n; i++) {
            const t = a0 + (ccw ? -1 : 1) * span * i / n, ex = rx * Math.cos(t), ey = ry * Math.sin(t);
            this.c.push([i === 0 && !this.c.length ? "M" : "L", cx + ex * cr - ey * sr, cy + ex * sr + ey * cr]);
        }
    }
    bezierCurveTo(a, b, c, d, x, y) { this.c.push(["C", a, b, c, d, x, y]); }
}
const SVG_NS = ["http:", "", "www.w3.org", "2000", "svg"].join("/"); // the SVG namespace: a name, never fetched (the page loads nothing)
class SvgCtx {
    constructor(w, h) {
        this.out = [];
        this.defs = [];
        this.k = 0;
        this.st = { m: [1, 0, 0, 1, 0, 0], fillStyle: "#000", strokeStyle: "#000", lineWidth: 1, lineCap: "butt", lineJoin: "miter", globalAlpha: 1, dash: [], font: "10px sans-serif", textAlign: "start", textBaseline: "alphabetic", clip: null };
        this.stack = [];
        this.path = new RecPath();
        this.canvas = { width: w, height: h };
        this.meas = document.createElement("canvas").getContext("2d");
    }
    get fillStyle() { return this.st.fillStyle; }
    set fillStyle(v) { this.st.fillStyle = v; }
    get strokeStyle() { return this.st.strokeStyle; }
    set strokeStyle(v) { this.st.strokeStyle = v; }
    get lineWidth() { return this.st.lineWidth; }
    set lineWidth(v) { this.st.lineWidth = v; }
    get lineCap() { return this.st.lineCap; }
    set lineCap(v) { this.st.lineCap = v; }
    get lineJoin() { return this.st.lineJoin; }
    set lineJoin(v) { this.st.lineJoin = v; }
    get globalAlpha() { return this.st.globalAlpha; }
    set globalAlpha(v) { this.st.globalAlpha = v; }
    get font() { return this.st.font; }
    set font(v) { this.st.font = v; }
    get textAlign() { return this.st.textAlign; }
    set textAlign(v) { this.st.textAlign = v; }
    get textBaseline() { return this.st.textBaseline; }
    set textBaseline(v) { this.st.textBaseline = v; }
    set shadowColor(v) { }
    set shadowBlur(v) { }
    set shadowOffsetX(v) { }
    set shadowOffsetY(v) { }
    save() { this.stack.push({ ...this.st, m: [...this.st.m], dash: [...this.st.dash] }); }
    restore() { if (this.stack.length)
        this.st = this.stack.pop(); }
    setTransform(a, b, c, d, e, f) { this.st.m = [a, b, c, d, e, f]; }
    transform(a, b, c, d, e, f) { const [A, B, C, D, E, F] = this.st.m; this.st.m = [A * a + C * b, B * a + D * b, A * c + C * d, B * c + D * d, A * e + C * f + E, B * e + D * f + F]; }
    translate(x, y) { this.transform(1, 0, 0, 1, x, y); }
    scale(x, y) { this.transform(x, 0, 0, y, 0, 0); }
    rotate(t) { const c = Math.cos(t), s = Math.sin(t); this.transform(c, s, -s, c, 0, 0); }
    setLineDash(d) { this.st.dash = [...d]; }
    getLineDash() { return [...this.st.dash]; }
    beginPath() { this.path = new RecPath(); }
    moveTo(x, y) { this.path.moveTo(x, y); }
    lineTo(x, y) { this.path.lineTo(x, y); }
    closePath() { this.path.closePath(); }
    rect(x, y, w, h) { this.path.rect(x, y, w, h); }
    arc(...a) { this.path.arc(...a); }
    ellipse(...a) { this.path.ellipse(...a); }
    bezierCurveTo(...a) { this.path.bezierCurveTo(...a); }
    measureText(t) { this.meas.font = this.st.font; return this.meas.measureText(t); }
    _scale() { const [a, b, c, d] = this.st.m; return Math.sqrt(Math.abs(a * d - b * c)) || 1; }
    _d(p) {
        const [a, b, c, d, e, f] = this.st.m, X = (x, y) => (a * x + c * y + e).toFixed(2), Y = (x, y) => (b * x + d * y + f).toFixed(2);
        return p.c.map(o => o[0] === "Z" ? "Z" : o[0] === "C" ? `C${X(o[1], o[2])} ${Y(o[1], o[2])} ${X(o[3], o[4])} ${Y(o[3], o[4])} ${X(o[5], o[6])} ${Y(o[5], o[6])}` : `${o[0]}${X(o[1], o[2])} ${Y(o[1], o[2])}`).join("");
    }
    _clip() { return this.st.clip ? ` clip-path="url(#${this.st.clip})"` : ""; }
    _alpha() { return this.st.globalAlpha < 1 ? ` opacity="${this.st.globalAlpha.toFixed(3)}"` : ""; }
    fill(p, rule) {
        if (typeof p === "string") {
            rule = p;
            p = null;
        }
        const d = this._d(p || this.path);
        if (!d)
            return;
        this.out.push(`<path d="${d}" fill="${this.st.fillStyle}"${rule === "evenodd" ? ' fill-rule="evenodd"' : ""}${this._alpha()}${this._clip()}/>`);
    }
    stroke(p) {
        const d = this._d(p || this.path);
        if (!d)
            return;
        const k = this._scale(), dash = this.st.dash.length ? ` stroke-dasharray="${this.st.dash.map(v => (v * k).toFixed(2)).join(" ")}"` : "";
        this.out.push(`<path d="${d}" fill="none" stroke="${this.st.strokeStyle}" stroke-width="${(this.st.lineWidth * k).toFixed(3)}" stroke-linecap="${this.st.lineCap}" stroke-linejoin="${this.st.lineJoin}"${dash}${this._alpha()}${this._clip()}/>`);
    }
    fillRect(x, y, w, h) { const p = new RecPath(); p.rect(x, y, w, h); this.fill(p); }
    strokeRect(x, y, w, h) { const p = new RecPath(); p.rect(x, y, w, h); this.stroke(p); }
    clearRect() { }
    clip(p, rule) { if (typeof p === "string") {
        rule = p;
        p = null;
    } const id = `c${this.k++}`; this.defs.push(`<clipPath id="${id}"><path d="${this._d(p || this.path)}"${rule === "evenodd" ? ' clip-rule="evenodd"' : ""}/></clipPath>`); this.st.clip = id; }
    fillText(t, x, y) {
        const [a, b, c, d, e, f] = this.st.m, anchor = { center: "middle", right: "end", end: "end" }[this.st.textAlign] || "start";
        const base = { middle: "central", top: "hanging", hanging: "hanging", bottom: "text-after-edge" }[this.st.textBaseline] || "alphabetic";
        this.out.push(`<text transform="matrix(${[a, b, c, d, e, f].map(v => +v.toFixed(5)).join(" ")})" x="${x}" y="${y}" style="font:${esc(this.st.font)}" fill="${this.st.fillStyle}" text-anchor="${anchor}" dominant-baseline="${base}"${this._alpha()}${this._clip()}>${esc(t)}</text>`);
    }
    drawImage(img, x, y, w, h) {
        const [a, b, c, d, e, f] = this.st.m;
        if (!img || !img.src)
            return;
        this.out.push(`<image href="${esc(img.src)}" x="${x}" y="${y}" width="${w ?? img.width}" height="${h ?? img.height}" transform="matrix(${[a, b, c, d, e, f].join(" ")})" preserveAspectRatio="none"${this._alpha()}${this._clip()}/>`);
    }
    svg(w, h, size) { return `<svg xmlns="${SVG_NS}" viewBox="0 0 ${w} ${h}" ${size || `width="${w}" height="${h}"`}><title>${esc(DOC ? DOC.name : "view")}</title><defs>${this.defs.join("")}</defs>${this.out.join("\n")}</svg>`; }
}
function viewSvg(size) {
    if (!S || st.mode3d)
        return null;
    const real = ctx, realDpr = dpr, rec = new SvgCtx(W, H);
    const board = !isSch();
    setCtx(rec);
    setDpr(1);
    if (board) {
        setP2D(RecPath);
        buildCaches();
        if (S.diff)
            S.diff.cache = null;
    }
    try {
        draw();
    }
    finally {
        setCtx(real);
        setDpr(realDpr);
        if (board) {
            setP2D(Path2D);
            buildCaches();
            if (S.diff)
                S.diff.cache = null;
        }
        draw();
    }
    return rec.svg(W, H, size);
}
function saveSvg() { const svg = viewSvg(); if (!svg) {
    showInfo("SVG: leave the 3D view first (D).");
    return;
} download(svg, (DOC ? DOC.name : "view") + ".svg", "image/svg+xml"); }
function printView(k = "fit") {
    const size = k === "fit" ? 'width="100%" height="100%" preserveAspectRatio="xMidYMid meet"' : `width="${(W / view.s * +k).toFixed(3)}mm" height="${(H / view.s * +k).toFixed(3)}mm"`;
    const svg = viewSvg(size);
    if (!svg) {
        showInfo("Print: leave the 3D view first (D).");
        return;
    }
    const f = document.createElement("iframe");
    f.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0";
    document.body.appendChild(f);
    const scale = k === "fit" ? "fit to page" : `scale ${k}:1`;
    f.contentDocument.open();
    f.contentDocument.write(`<!doctype html><html><head><title>${esc(DOC ? DOC.name : "view")}</title><style>@page { margin: 10mm } html, body { margin: 0; height: 100% } svg { display: block; ${k === "fit" ? "width: 100%; height: 95vh" : ""} } p { font: 9pt system-ui; margin: 2mm 0 0 }</style></head><body>${svg}<p>${esc(DOC ? DOC.name : "")} · ${scale} · Fenolite viewer</p></body></html>`);
    f.contentDocument.close();
    setTimeout(() => { f.contentWindow.focus(); f.contentWindow.print(); setTimeout(() => f.remove(), 2000); }, 200);
}
// ---- table/table.ts
// ================================================================== tables (c0190): a BOM document, an output job
const TBL = { sort: -1, up: true, q: "" };
function loadTable(scene) {
    setS(scene);
    st.mode3d = false;
    document.body.classList.remove("sch", "lib");
    document.body.classList.add("table");
    cv.style.display = "none";
    glc.style.display = "none";
    $("cube").style.display = "none";
    document.body.classList.remove("mode3d");
    setDocTitle(scene.meta.name);
    $("notes").innerHTML = (scene.meta.notes || []).map(esc).join("<br>") + `<br>Read by the ${esc(scene.meta.backend || "?")} backend, evidence ${esc(scene.meta.evidence || "?")}.`;
    TBL.sort = -1;
    TBL.up = true;
    TBL.q = "";
    const box = $("tablewrap");
    box.style.display = "block";
    box.innerHTML = `<div class="tblhead"><b>${esc(scene.title || scene.meta.name)}</b><input id="tblFilter" placeholder="Filter the rows…"><small id="tblCount"></small></div>` +
        `<table class="tbl"><thead><tr>${scene.columns.map((c, k) => `<th data-k="${k}" title="Sort">${esc(c)}</th>`).join("")}</tr></thead><tbody id="tblBody"></tbody></table>`;
    box.querySelectorAll("th").forEach(th => th.onclick = () => { const k = +th.dataset.k; TBL.up = TBL.sort === k ? !TBL.up : true; TBL.sort = k; renderRows(); });
    $("tblFilter").oninput = e => { TBL.q = e.target.value; renderRows(); };
    renderRows();
    showInfo(null);
}
function renderRows() {
    const sc = S, q = TBL.q.trim().toLowerCase();
    const idx = sc.rows.map((r, i) => i).filter(i => !q || sc.rows[i].some(v => String(v).toLowerCase().includes(q)));
    if (TBL.sort >= 0)
        idx.sort((a, b) => natural(String(sc.rows[a][TBL.sort]), String(sc.rows[b][TBL.sort])) * (TBL.up ? 1 : -1));
    $("tablewrap").querySelectorAll("th").forEach(th => { const k = +th.dataset.k; th.textContent = sc.columns[k] + (k === TBL.sort ? (TBL.up ? " ▲" : " ▼") : ""); });
    $("tblBody").innerHTML = idx.map(i => {
        const go = ((sc.docs || [])[i] || []).length || ((sc.refs || [])[i] || []).length;
        const why = ((sc.docs || [])[i] || []).length ? "Open the document it binds" : "Select these parts on the board";
        return `<tr data-i="${i}"${go ? ` class="link" title="${why}"` : ""}>${sc.rows[i].map(v => `<td>${linkify(v)}</td>`).join("")}</tr>`;
    }).join("");
    $("tblBody").querySelectorAll("tr.link").forEach(tr => tr.onclick = ev => { if (ev.target.tagName !== "A")
        tableRow(+tr.dataset.i); });
    $("tblCount").textContent = `${idx.length} of ${sc.rows.length} rows`;
}
async function tableRow(i) {
    const docs = (S.docs || [])[i] || [], refs = (S.refs || [])[i] || [];
    if (docs.length) {
        const d = docs[0] === "[bom]" ? allDocs().find(x => x.kind === "bom") : docByFile(docs[0]);
        if (d)
            await openDoc(d);
        else
            showInfo(`${esc(docs[0])} is not a document of this project.`);
        return;
    }
    if (!refs.length)
        return;
    const d = allDocs().find(x => x.kind === "pcb" && x.viewable && x.present);
    if (!d) {
        showInfo("The project holds no board to show these parts on.");
        return;
    }
    const shown = await openDoc(d);
    if (!shown || shown !== navigation)
        return;
    const text = refs.map(r => `ref:${r}`).join(" | ");
    $("query").value = text;
    applyQuery(text, true);
}
// ---- core/input.ts
function flip() { view.mirror = !view.mirror; refreshToolbar(); draw(); }
function toggle(key) { st[key] = !st[key]; if (key === "measure" && !st.measure)
    st.mpts = []; refreshToolbar(); draw(); }
function find(q) {
    q = q.trim().toLowerCase();
    if (!q || !S)
        return;
    if (isSch()) {
        schFind(q);
        return;
    }
    const ci = S.comps.findIndex(c => c.ref.toLowerCase() === q);
    if (ci >= 0) {
        st.selComp = ci;
        st.selNet = -1;
        const b = S.comps[ci].bbox;
        if (b)
            fit([b[0] - 5, b[1] - 5, b[2] + 5, b[3] + 5]);
        inspect(() => partModel(ci));
        draw();
        return;
    }
    const ni = S.nets.findIndex(n => n.toLowerCase() === q);
    if (ni >= 0) {
        st.selNet = ni;
        st.selComp = -1;
        inspect(() => netModel(ni));
        draw();
        return;
    }
    showInfo(`Nothing named <b>${esc(q)}</b> on this board.`);
}
function setSidebar(open) {
    $("app").classList.toggle("sidebar-open", open);
    refreshToolbar();
}
function zoomBy(f) { view.s = Math.min(Math.max(view.s * f, 0.2), 400); draw(); }
let drag = null;
cv.addEventListener("mousedown", e => {
    if (document.activeElement && document.activeElement.blur)
        document.activeElement.blur(); // shortcuts follow the board
    drag = { x: e.offsetX, y: e.offsetY, cx: view.cx, cy: view.cy, moved: false };
});
window.addEventListener("mouseup", e => {
    if (!drag)
        return;
    const d = drag;
    drag = null;
    if (d.moved || e.target !== cv)
        return;
    const [x, y] = s2w(e.offsetX, e.offsetY);
    if (st.measure) {
        measureClick(e.offsetX, e.offsetY, e.altKey);
        return;
    }
    if (st.marking) {
        markClick(x, y);
        return;
    }
    if (st.edge && !isSch()) {
        edgeClick(e.offsetX, e.offsetY);
        return;
    }
    if (isSch())
        schSelect(schPick(e.offsetX, e.offsetY));
    else
        select(pick(e.offsetX, e.offsetY), [x, y]);
});
cv.addEventListener("dblclick", e => {
    if (!S)
        return;
    if (isSch()) {
        schDouble(e.offsetX, e.offsetY);
        return;
    }
    const h = pick(e.offsetX, e.offsetY), ci = h ? h.pr[4] : -1;
    if (ci >= 0)
        crossProbe(S.comps[ci].ref, "schematic");
});
cv.addEventListener("contextmenu", e => { if (isSch())
    e.preventDefault(); });
function showCoord(x, y) {
    st.mouse = [x, y];
    if (!(st.measure && st.mpts.length))
        $("coord").textContent = isSch()
            ? `X ${fmtLen(x - S.sheet.origin[0])}   Y ${fmtLen(S.sheet.origin[1] - y)}` : `X ${fmtLen(x)}   Y ${fmtLen(y)}`;
}
cv.addEventListener("mousemove", e => {
    if (!S)
        return;
    const [x, y] = s2w(e.offsetX, e.offsetY);
    showCoord(x, y);
    if (drag) {
        const dx = e.offsetX - drag.x, dy = e.offsetY - drag.y;
        if (Math.abs(dx) + Math.abs(dy) > 3)
            drag.moved = true;
        view.cx = drag.cx - m() * dx / view.s;
        view.cy = drag.cy - dy / view.s;
        draw();
    }
    else if (st.measure) {
        st.mhover = snap(x, y, e.altKey);
        draw();
    }
});
cv.addEventListener("wheel", e => {
    e.preventDefault();
    const [x, y] = s2w(e.offsetX, e.offsetY);
    const f = Math.exp(-e.deltaY * 0.0015);
    view.s = Math.min(Math.max(view.s * f, 0.2), 400);
    const [x2, y2] = s2w(e.offsetX, e.offsetY);
    view.cx += x - x2;
    view.cy += y - y2;
    draw();
}, { passive: false });
// The shortcuts (c0235, c0300): looked up in the command registry, never in form controls, dialogs or the project
// review, during composition, after default prevention or with Ctrl, Meta or Alt; the one exception is the
// palette chord, Ctrl+K (Cmd+K on macOS), which also works from a focused field.
window.addEventListener("keydown", e => {
    if (e.defaultPrevented || e.isComposing)
        return;
    if ((IS_MAC ? e.metaKey : e.ctrlKey) && !e.altKey && !e.shiftKey && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        openPalette();
        return;
    }
    const target = e.target;
    if (e.ctrlKey || e.metaKey || e.altKey ||
        (target instanceof Element && (target.closest("input, select, textarea, dialog[open], #projectReview") || target.isContentEditable)))
        return;
    const c = commandForKey(e);
    if (!c)
        return;
    if (c.keys.includes("PageUp") || c.keys.includes("PageDown"))
        e.preventDefault();
    c.run();
    refreshToolbar();
});
// ---- sch/scene.ts
// ================================================================== schematic view (scene kind "schematic")
// A sheet drawn as Altium Designer draws it: the file's own colours and fonts on its paper, a line grid, a grey
// workspace around it. Units on the page are millimetres, Y downwards from the sheet's top-left corner.
const SCH = { sel: -1, selNet: -1, selComp: -1, images: new Map(), byObj: null, filter: "" };
const WORKSPACE = "#4a4d52", SEL = "#00b050";
const isSch = () => !!(S && S.kind === "schematic");
const MIL = 0.0254;
function toMMsch(sc) {
    if (sc.mm)
        return sc;
    diffToMM(sc);
    checkToMM(sc);
    const f = v => v * MM, fb = b => b ? b.map(f) : b;
    for (const p of sc.prims) {
        if (p.p)
            p.p = p.p.map(f);
        if (p.b)
            p.b = p.b.map(f);
        for (const k of ["x", "y", "rx", "ry", "w", "m", "sz", "gw", "th"])
            if (typeof p[k] === "number")
                p[k] = p[k] * MM;
        if (p.rr)
            p.rr = p.rr.map(f);
        p.bb = primBox(p);
    }
    for (const o of sc.objects)
        o.b = fb(o.b);
    for (const c of sc.comps)
        c.b = fb(c.b);
    for (const fo of sc.fonts)
        fo.emm = fo.em * MM;
    const sh = sc.sheet;
    for (const k of ["w", "h", "grid", "margin", "x0", "y0"])
        if (typeof sh[k] === "number")
            sh[k] *= MM;
    sh.x0 = sh.x0 || 0;
    sh.y0 = sh.y0 || 0;
    sh.origin = sh.origin ? sh.origin.map(f) : [0, sh.h];
    if (sh.text === "stroke")
        sc.comps.forEach(c => { c.hidden = c.ref.startsWith("#"); });
    sc.bounds = sc.bounds.map(f);
    sc.mm = true;
    return sc;
}
function primBox(p) {
    const w = (p.w || 0) / 2;
    if (p.k === "l" || p.k === "g" || p.k === "b") {
        let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
        for (let i = 0; i < p.p.length; i += 2) {
            x0 = Math.min(x0, p.p[i]);
            x1 = Math.max(x1, p.p[i]);
            y0 = Math.min(y0, p.p[i + 1]);
            y1 = Math.max(y1, p.p[i + 1]);
        }
        return [x0 - w, y0 - w, x1 + w, y1 + w];
    }
    if (p.k === "r" || p.k === "x" || p.k === "i")
        return [p.b[0] - w, p.b[1] - w, p.b[2] + w, p.b[3] + w];
    if (p.k === "e" || p.k === "a")
        return [p.x - p.rx - w, p.y - p.ry - w, p.x + p.rx + w, p.y + p.ry + w];
    return null; // texts: measured when drawn
}
// ---- sch/draw.ts
function fontCss(fo, px) { return `${fo.italic ? "italic " : ""}${fo.bold ? "bold " : ""}${px.toFixed(2)}px "${fo.name}", "Times New Roman", Times, serif`; }
function schAlpha(p) {
    if (SCH.selNet < 0)
        return 1;
    const o = p.o >= 0 ? S.objects[p.o] : null;
    return o && o.net === SCH.selNet ? 1 : 0.22;
}
function dashOf(d, w) { const u = Math.max(w, 0.1); return d === 1 ? [u * 4, u * 3] : d === 2 ? [u, u * 2] : d === 3 ? [u * 4, u * 2, u, u * 2] : []; }
function lineShape(g, x, y, fx, fy, shape, size, color, w) {
    const L = [0.5, 1, 1.6, 2.4][size || 0] || 1, a = Math.atan2(y - fy, x - fx), c = Math.cos(a), s = Math.sin(a);
    const P = (u, v) => [x + u * c - v * s, y + u * s + v * c];
    g.beginPath();
    if (shape === 1 || shape === 2) {
        const [ax, ay] = P(-L, -L / 2), [bx, by] = P(-L, L / 2);
        g.moveTo(ax, ay);
        g.lineTo(x, y);
        g.lineTo(bx, by);
        if (shape === 2) {
            g.closePath();
            g.fillStyle = color;
            g.fill();
        }
        g.stroke();
    }
    else if (shape === 3 || shape === 4) {
        const [ax, ay] = P(L, -L / 2), [bx, by] = P(L, L / 2);
        g.moveTo(ax, ay);
        g.lineTo(x, y);
        g.lineTo(bx, by);
        if (shape === 4) {
            g.closePath();
            g.fillStyle = color;
            g.fill();
        }
        g.stroke();
    }
    else if (shape === 5) {
        g.arc(x, y, L / 2, 0, 2 * Math.PI);
        g.fillStyle = color;
        g.fill();
    }
    else if (shape === 6) {
        g.fillStyle = color;
        g.fillRect(x - L / 2, y - L / 2, L, L);
    }
}
function roundRectPath(g, b, rx, ry) {
    const [x0, y0, x1, y1] = b;
    rx = Math.min(rx, (x1 - x0) / 2);
    ry = Math.min(ry, (y1 - y0) / 2);
    g.beginPath();
    g.moveTo(x0 + rx, y0);
    g.lineTo(x1 - rx, y0);
    g.ellipse(x1 - rx, y0 + ry, rx, ry, 0, -Math.PI / 2, 0);
    g.lineTo(x1, y1 - ry);
    g.ellipse(x1 - rx, y1 - ry, rx, ry, 0, 0, Math.PI / 2);
    g.lineTo(x0 + rx, y1);
    g.ellipse(x0 + rx, y1 - ry, rx, ry, 0, Math.PI / 2, Math.PI);
    g.lineTo(x0, y0 + ry);
    g.ellipse(x0 + rx, y0 + ry, rx, ry, 0, Math.PI, 1.5 * Math.PI);
    g.closePath();
}
function strokeW(w) { return Math.max(w, 1 / view.s); }
function drawStrokeText(p, alpha) {
    if (p.sz * view.s < 1.5)
        return;
    const lines = p.s.split("\n"), adv = 1.5 * p.gw, step = p.sz * 1.4, deg = (p.rot || 0) * 90, a = deg * Math.PI / 180;
    ctx.globalAlpha = alpha;
    ctx.strokeStyle = p.c;
    ctx.lineWidth = Math.max(p.th, 1 / view.s);
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    const n = lines.length, first = p.v === "top" ? 0 : p.v === "bottom" ? -(n - 1) : -(n - 1) / 2;
    let wMax = 0;
    ctx.beginPath();
    lines.forEach((ln, i) => {
        const off = (first + i) * step, x = p.x + Math.sin(a) * off, y = p.y + Math.cos(a) * off;
        const t = ["", x, y, p.sz, p.gw, p.th, deg, p.h, p.v, false, ln, -1];
        for (const pl of textPolylines(t)) {
            ctx.moveTo(pl[0][0], pl[0][1]);
            for (let k = 1; k < pl.length; k++)
                ctx.lineTo(pl[k][0], pl[k][1]);
            if (pl.length === 1)
                ctx.lineTo(pl[0][0] + 1e-4, pl[0][1]);
        }
        const wl = [...ln].length * adv - 2 * p.gw / 4;
        wMax = Math.max(wMax, wl);
        if (p.ol && p.ol.length && n === 1) {
            const x0 = p.h === "left" ? 0 : p.h === "right" ? -wl : -wl / 2, top = p.v === "top" ? 0 : p.v === "bottom" ? -p.sz : -p.sz / 2;
            const ly = top - p.sz * 0.2, c = Math.cos(a), s2 = Math.sin(a), P = lx => [x + lx * c + ly * s2, y - lx * s2 + ly * c];
            for (const k of p.ol) {
                const [ax, ay] = P(x0 + k * adv), [bx, by] = P(x0 + k * adv + p.gw);
                ctx.moveTo(ax, ay);
                ctx.lineTo(bx, by);
            }
        }
    });
    ctx.stroke();
    p.sb = [wMax, n * step];
}
function drawText(p, alpha) {
    if (S.sheet.text === "stroke")
        return drawStrokeText(p, alpha);
    const fo = S.fonts[p.font] || S.fonts[0], px = fo.emm * view.s;
    if (px < 1.2)
        return;
    const [X, Y] = w2s(p.x, p.y);
    ctx.save();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.globalAlpha = alpha;
    ctx.translate(X, Y);
    if (p.rot)
        ctx.rotate(-p.rot * Math.PI / 2);
    ctx.font = fontCss(fo, px);
    ctx.fillStyle = p.c;
    ctx.textAlign = p.h;
    ctx.textBaseline = p.v === "center" ? "middle" : p.v === "top" ? "top" : "bottom";
    ctx.fillText(p.s, 0, 0);
    const wAll = ctx.measureText(p.s).width, x0 = p.h === "left" ? 0 : p.h === "right" ? -wAll : -wAll / 2;
    const top = p.v === "top" ? 0 : p.v === "center" ? -px / 2 : -px, lw = Math.max(1, px / 14);
    p.sb = [wAll / view.s, px / view.s]; // measured size, for the hit test
    if (p.ol && p.ol.length) {
        ctx.strokeStyle = p.c;
        ctx.lineWidth = lw;
        ctx.beginPath();
        for (const i of p.ol) {
            const a = ctx.measureText(p.s.slice(0, i)).width, b = ctx.measureText(p.s.slice(0, i + 1)).width;
            ctx.moveTo(x0 + a, top + lw);
            ctx.lineTo(x0 + b, top + lw);
        }
        ctx.stroke();
    }
    if (fo.underline) {
        ctx.strokeStyle = p.c;
        ctx.lineWidth = lw;
        ctx.beginPath();
        ctx.moveTo(x0, top + px);
        ctx.lineTo(x0 + wAll, top + px);
        ctx.stroke();
    }
    ctx.restore();
}
function wrapLines(g, text, width, wrap) {
    const out = [];
    for (const para of text.split("\n")) {
        if (!wrap) {
            out.push(para);
            continue;
        }
        let line = "";
        for (const word of para.split(/(\s+)/)) {
            const t = line + word;
            if (line && g.measureText(t).width > width) {
                out.push(line.trimEnd());
                line = word.trimStart();
            }
            else
                line = t;
        }
        out.push(line);
    }
    return out;
}
function drawFrame(p, alpha) {
    const [x0, y0, x1, y1] = p.b;
    ctx.globalAlpha = alpha;
    if (p.f) {
        ctx.fillStyle = p.f;
        ctx.fillRect(x0, y0, x1 - x0, y1 - y0);
    }
    if (p.bc) {
        ctx.strokeStyle = p.bc;
        ctx.lineWidth = strokeW(0.1);
        ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
    }
    const fo = S.fonts[p.font] || S.fonts[0], px = fo.emm * view.s;
    if (px < 1.2)
        return;
    const [X0, Y0] = w2s(x0, y0), [X1, Y1] = w2s(x1, y1), m = (p.m || 0) * view.s;
    ctx.save();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.globalAlpha = alpha;
    ctx.beginPath();
    ctx.rect(X0, Y0, X1 - X0, Y1 - Y0);
    ctx.clip();
    ctx.font = fontCss(fo, px);
    ctx.fillStyle = p.tc;
    ctx.textBaseline = "top";
    const lines = wrapLines(ctx, p.s, X1 - X0 - 2 * m, p.wrap), al = p.al === 1 ? "left" : p.al === 2 ? "right" : p.al === 0 ? "center" : "left";
    ctx.textAlign = al;
    const x = al === "left" ? X0 + m : al === "right" ? X1 - m : (X0 + X1) / 2;
    lines.forEach((ln, i) => ctx.fillText(ln, x, Y0 + m + i * px * 1.15));
    ctx.restore();
}
function drawImage(p, alpha) {
    const [x0, y0, x1, y1] = p.b;
    ctx.globalAlpha = alpha;
    if (p.src) {
        let im = SCH.images.get(p.src);
        if (!im) {
            im = new Image();
            im.onload = () => draw();
            im.src = p.src;
            SCH.images.set(p.src, im);
        }
        if (im.complete && im.naturalWidth) {
            ctx.drawImage(im, x0, y0, x1 - x0, y1 - y0);
            return;
        }
    }
    ctx.strokeStyle = "#888";
    ctx.lineWidth = strokeW(0.1);
    ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.moveTo(x1, y0);
    ctx.lineTo(x0, y1);
    ctx.stroke();
}
function drawPrim(p, alpha) {
    const g = ctx;
    g.globalAlpha = alpha;
    g.strokeStyle = p.c;
    g.lineWidth = strokeW(p.w || 0);
    g.lineCap = "round";
    g.lineJoin = "round";
    switch (p.k) {
        case "l": {
            const q = p.p;
            g.setLineDash(p.d ? dashOf(p.d, p.w) : []);
            g.lineCap = p.d ? "butt" : "round";
            g.beginPath();
            g.moveTo(q[0], q[1]);
            for (let i = 2; i < q.length; i += 2)
                g.lineTo(q[i], q[i + 1]);
            if (q.length === 2)
                g.lineTo(q[0] + 1e-4, q[1]);
            g.stroke();
            g.setLineDash([]);
            if (p.s0 && q.length >= 4)
                lineShape(g, q[0], q[1], q[2], q[3], p.s0, p.ss, p.c, p.w);
            if (p.s1 && q.length >= 4) {
                const n = q.length;
                lineShape(g, q[n - 2], q[n - 1], q[n - 4], q[n - 3], p.s1, p.ss, p.c, p.w);
            }
            break;
        }
        case "g": {
            const q = p.p;
            g.beginPath();
            g.moveTo(q[0], q[1]);
            for (let i = 2; i < q.length; i += 2)
                g.lineTo(q[i], q[i + 1]);
            g.closePath();
            if (p.f) {
                g.fillStyle = p.f;
                g.fill();
            }
            g.stroke();
            break;
        }
        case "r": {
            const [x0, y0, x1, y1] = p.b;
            if (p.rr)
                roundRectPath(g, p.b, p.rr[0], p.rr[1]);
            else {
                g.beginPath();
                g.rect(x0, y0, x1 - x0, y1 - y0);
            }
            if (p.f) {
                g.globalAlpha = alpha * (p.ta ? 0.5 : 1);
                g.fillStyle = p.f;
                g.fill();
                g.globalAlpha = alpha;
            }
            g.stroke();
            break;
        }
        case "e":
            g.beginPath();
            g.ellipse(p.x, p.y, Math.max(p.rx, 1e-4), Math.max(p.ry, 1e-4), 0, 0, 2 * Math.PI);
            if (p.f) {
                g.fillStyle = p.f;
                g.fill();
            }
            if (p.w || !p.f)
                g.stroke();
            break;
        case "a": {
            let a0 = p.a0, a1 = p.a1;
            const full = Math.abs(a1 - a0) >= 360 || a0 === a1;
            g.beginPath();
            if (p.pie && !full)
                g.moveTo(p.x, p.y);
            g.ellipse(p.x, p.y, Math.max(p.rx, 1e-4), Math.max(p.ry, 1e-4), 0, full ? 0 : -a0 * Math.PI / 180, full ? 2 * Math.PI : -a1 * Math.PI / 180, !full);
            if (p.pie) {
                g.closePath();
                if (p.f) {
                    g.fillStyle = p.f;
                    g.fill();
                }
            }
            g.stroke();
            break;
        }
        case "b": {
            const q = p.p;
            g.beginPath();
            g.moveTo(q[0], q[1]);
            let i = 2;
            for (; i + 5 < q.length; i += 6)
                g.bezierCurveTo(q[i], q[i + 1], q[i + 2], q[i + 3], q[i + 4], q[i + 5]);
            for (; i < q.length; i += 2)
                g.lineTo(q[i], q[i + 1]);
            g.stroke();
            break;
        }
        case "t":
            drawText(p, alpha);
            break;
        case "x":
            drawFrame(p, alpha);
            break;
        case "i":
            drawImage(p, alpha);
            break;
    }
}
function visibleBox() { const [ax, ay] = s2w(0, 0), [bx, by] = s2w(W, H); return [Math.min(ax, bx), Math.min(ay, by), Math.max(ax, bx), Math.max(ay, by)]; }
function drawGrid(sh) {
    if (!sh.grid || sh.grid * view.s < 8)
        return;
    const vb = visibleBox(), g = sh.grid, ox = sh.origin ? sh.origin[0] : 0, oy = sh.origin ? sh.origin[1] : 0, X0 = sh.x0 || 0, Y0 = sh.y0 || 0, X1 = X0 + sh.w, Y1 = Y0 + sh.h;
    const x0 = ox + Math.ceil((Math.max(X0, vb[0]) - ox) / g) * g, x1 = Math.min(X1, vb[2]), y0 = oy + Math.ceil((Math.max(Y0, vb[1]) - oy) / g) * g, y1 = Math.min(Y1, vb[3]);
    if (sh.text === "stroke") { // KiCad draws its grid as dots
        ctx.globalAlpha = 1;
        ctx.fillStyle = sh.grid_color || shade(sh.color, 0.3);
        const d = 1.4 / view.s;
        for (let x = x0; x <= x1; x += g)
            for (let y = y0; y <= y1; y += g)
                ctx.fillRect(x - d / 2, y - d / 2, d, d);
        return;
    }
    ctx.globalAlpha = 1;
    ctx.strokeStyle = shade(sh.color, 0.08);
    ctx.lineWidth = 1 / view.s;
    ctx.beginPath();
    for (let x = x0; x <= x1; x += g) {
        ctx.moveTo(x, Math.max(Y0, vb[1]));
        ctx.lineTo(x, Math.min(Y1, vb[3]));
    }
    for (let y = y0; y <= y1; y += g) {
        ctx.moveTo(Math.max(X0, vb[0]), y);
        ctx.lineTo(Math.min(X1, vb[2]), y);
    }
    ctx.stroke();
}
function shade(hex, f) { const n = parseInt(hex.slice(1), 16); const c = [n >> 16, (n >> 8) & 255, n & 255].map(v => Math.round(v * (1 - f))); return `rgb(${c[0]},${c[1]},${c[2]})`; }
function drawSch() {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalAlpha = 1;
    ctx.fillStyle = S.sheet.workspace || WORKSPACE;
    ctx.fillRect(0, 0, cv.width, cv.height);
    worldTf();
    const sh = S.sheet;
    ctx.save();
    ctx.shadowColor = "#0008";
    ctx.shadowBlur = 12;
    ctx.shadowOffsetX = 3;
    ctx.shadowOffsetY = 3;
    ctx.fillStyle = sh.color;
    ctx.fillRect(sh.x0 || 0, sh.y0 || 0, sh.w, sh.h);
    ctx.restore();
    drawGrid(sh);
    const vb = visibleBox(), pad = 2;
    for (const p of S.prims) {
        const b = p.bb;
        if (b && (b[2] < vb[0] - pad || b[0] > vb[2] + pad || b[3] < vb[1] - pad || b[1] > vb[3] + pad))
            continue;
        drawPrim(p, schAlpha(p));
    }
    ctx.globalAlpha = 1;
    const sb = SCH.selComp >= 0 ? S.comps[SCH.selComp].b : SCH.sel >= 0 && SCH.selNet < 0 ? S.objects[SCH.sel].b : null;
    if (sb) {
        const e = 4 / view.s;
        ctx.strokeStyle = SEL;
        ctx.lineWidth = 1.5 / view.s;
        ctx.setLineDash([5 / view.s, 3 / view.s]);
        ctx.strokeRect(sb[0] - e, sb[1] - e, sb[2] - sb[0] + 2 * e, sb[3] - sb[1] + 2 * e);
        ctx.setLineDash([]);
    }
    drawSchDiff();
    drawCheck();
    drawMarks();
    linkLater();
    if (S.variants)
        drawVariantMarks(S.comps.map(c => [c.group || c.ref, c.b]));
    drawMeasure();
    $("zoomv").textContent = `Zoom ${(view.s * MIL * 100).toFixed(0)} %`;
    refreshStatus();
}
// ---- sch/hit.ts
// --- hit test
function schHitPrim(p, x, y, tol) {
    switch (p.k) {
        case "l": {
            const q = p.p;
            if (q.length === 2)
                return Math.hypot(x - q[0], y - q[1]) <= tol + p.w / 2;
            for (let i = 0; i + 3 < q.length; i += 2)
                if (segDist(x, y, q[i], q[i + 1], q[i + 2], q[i + 3]) <= p.w / 2 + tol)
                    return true;
            return false;
        }
        case "g": return inRing(x, y, p.p) || p.p.some((_, i) => i % 2 === 0 && i + 3 < p.p.length && segDist(x, y, p.p[i], p.p[i + 1], p.p[i + 2], p.p[i + 3]) <= tol);
        case "r":
        case "x":
        case "i": {
            const b = p.b;
            return x >= b[0] - tol && x <= b[2] + tol && y >= b[1] - tol && y <= b[3] + tol;
        }
        case "e":
        case "a": return ((x - p.x) / (p.rx + tol)) ** 2 + ((y - p.y) / (p.ry + tol)) ** 2 <= 1;
        case "b": {
            const q = p.p;
            for (let i = 0; i + 3 < q.length; i += 2)
                if (segDist(x, y, q[i], q[i + 1], q[i + 2], q[i + 3]) <= p.w / 2 + tol)
                    return true;
            return false;
        }
        case "t": {
            if (!p.sb)
                return false;
            const [w, h] = p.sb, c = [1, 0, -1, 0][p.rot || 0], s = [0, 1, 0, -1][p.rot || 0];
            const dx = x - p.x, dy = y - p.y, u = dx * c - dy * s, v = dx * s + dy * c; // into the text's own frame
            const u0 = p.h === "left" ? 0 : p.h === "right" ? -w : -w / 2, v0 = p.v === "top" ? 0 : p.v === "center" ? -h / 2 : -h;
            return u >= u0 - tol && u <= u0 + w + tol && v >= v0 - tol && v <= v0 + h + tol;
        }
    }
    return false;
}
const PRIORITY = { pin: 0, wire: 1, bus: 1, entryline: 1, junction: 1, label: 1, power: 1, port: 1, entry: 1, noerc: 1, harnessline: 1, comp: 2, sheet: 2, harness: 2, directive: 2, graphic: 3 };
function schPick(X, Y) {
    const [x, y] = s2w(X, Y), tol = 3 / view.s;
    let best = -1, bp = 9;
    for (let i = S.prims.length - 1; i >= 0; i--) {
        const p = S.prims[i];
        if (p.o < 0)
            continue;
        const b = p.bb;
        if (b && (x < b[0] - tol || x > b[2] + tol || y < b[1] - tol || y > b[3] + tol))
            continue;
        if (!schHitPrim(p, x, y, tol))
            continue;
        const pr = PRIORITY[S.objects[p.o].k] ?? 4;
        if (pr < bp) {
            bp = pr;
            best = p.o;
            if (pr === 0)
                break;
        }
    }
    if (best < 0)
        for (let i = 0; i < S.comps.length; i++) {
            const b = S.comps[i].b;
            if (b && x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3]) {
                best = S.objects.findIndex(o => o.k === "comp" && o.comp === i);
                break;
            }
        }
    return best;
}
// ---- sch/select.ts
function rows(list) { return `<table>${list.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${linkify(v)}</td></tr>`).join("")}</table>`; }
function compRows(ci) {
    const c = S.comps[ci];
    const r = [["Designator", c.ref], ["Comment", c.comment], ["Design Item ID", c.lib]];
    if (c.b)
        r.push(["Extent", fmtPair(c.b[2] - c.b[0], c.b[3] - c.b[1])]);
    if (c.description)
        r.push(["Description", c.description]);
    if (c.footprint)
        r.push(["Footprint", c.footprint]);
    const vs = variantOf(c.group || c.ref);
    const params = { ...(c.params || {}), ...((vs && vs.params) || {}) };
    for (const [k, v] of Object.entries(params))
        r.push([k, v]);
    if (vs)
        r.push([`Variant ${VARIANT}`, vs.kind]);
    return r;
}
function schSelect(oi) {
    SCH.sel = oi;
    SCH.selNet = -1;
    SCH.selComp = -1;
    if (oi < 0) {
        showInfo(null);
        buildNav();
        draw();
        return;
    }
    const o = S.objects[oi];
    if (o.comp >= 0 && o.k === "comp")
        SCH.selComp = o.comp;
    if (o.k !== "comp" && o.net >= 0) {
        SCH.selNet = o.net;
        const n = S.nets[o.net];
        shareNet(n.project || n.name);
    }
    inspect(() => schModel(oi));
    buildNav();
    draw();
}
const SCH_KIND = { comp: "component", wire: "wire", pin: "pin", sheet: "sheet" };
function schModel(oi) {
    const o = S.objects[oi], sections = [];
    if (o.k === "comp")
        sections.push(isection("Component", compRows(o.comp).map(([k, v]) => irow(k, v, /^https?:\/\//i.test(String(v)) ? { link: String(v) } : undefined))));
    else {
        sections.push(isection("Properties", (o.info || []).map(([k, v]) => irow(k, v, /^https?:\/\//i.test(String(v)) ? { link: String(v) } : undefined))));
        if (o.net >= 0) {
            const n = S.nets[o.net];
            sections.push(schNetSection(n), projectNetSection(n));
        }
        if (o.comp >= 0)
            sections.push(isection("Part", compRows(o.comp).map(([k, v]) => irow(k, v))));
    }
    const ci = o.comp >= 0 ? o.comp : -1, title = o.k === "comp" ? S.comps[o.comp].ref : (o.info || []).find(r => /^(Name|Text|Designator)$/.test(r[0]))?.[1] || o.k;
    return imodel(SCH_KIND[o.k] || "item", String(title), sections, { subtitle: o.k === "comp" ? S.comps[o.comp].comment || "" : o.k, target: { sch: true, comp: ci, net: o.net >= 0 ? o.net : -1 } });
}
function netBox(ni) { let b = null; for (const o of S.objects)
    if (o.net === ni && o.b)
        b = b ? [Math.min(b[0], o.b[0]), Math.min(b[1], o.b[1]), Math.max(b[2], o.b[2]), Math.max(b[3], o.b[3])] : [...o.b]; return b; }
// ---- sch/project-nets.ts
// ================================================================== project nets across sheets and the board (c0185)
let PROJ_NET = null;
const BC = !PREVIEW_MODE && "BroadcastChannel" in window ? new BroadcastChannel("fenolite-view") : null;
function shareNet(name) { PROJ_NET = name || null; if (BC)
    BC.postMessage({ net: PROJ_NET }); }
if (BC)
    BC.onmessage = e => { PROJ_NET = e.data && e.data.net || null; applyProjNet(); };
function projectNetSection(n) {
    if (!n.project)
        return null;
    const others = (n.sheets || []).filter(x => !S.meta || x !== S.meta.name), pins = n.project_pins || [];
    return isection("Project net", [irow("Name", n.project), irow("Pins", pins.length), others.length ? irow("Also on", others.join(", "), { sheets: others }) : irow("Sheets", "this sheet only"),
        pins.length ? irow("Pin list", pins.slice(0, 60).join(", ") + (pins.length > 60 ? " …" : ""), { mono: false }) : null]);
}
function schNetSection(n) { return isection("Net", [irow("Name", n.name || "(no name)"), irow("Pins", n.pins.length), n.pins.length ? irow("Pin list", n.pins.slice(0, 60).join(", ") + (n.pins.length > 60 ? " …" : "")) : null]); }
function schNetModel(ni) { const n = S.nets[ni]; return imodel("net", n.name || "(no name)", [schNetSection(n), projectNetSection(n)], { subtitle: "Net", target: { sch: true, net: ni, comp: -1 } }); }
function projectNetInfo(n) {
    if (!n.project)
        return "";
    const others = (n.sheets || []).filter(x => !S.meta || x !== S.meta.name);
    const links = others.map(x => `<a href="#" class="sheetlink" data-sheet="${esc(x)}">${esc(x)}</a>`).join(", ");
    return `<br><br><b>Project net ${esc(n.project)}</b>: ${(n.project_pins || []).length} pins` + (links ? `<br>Also on: ${links}` : "<br>On this sheet only") +
        `<br><small>${esc((n.project_pins || []).slice(0, 60).join(", "))}</small>`;
}
document.addEventListener("click", (e) => {
    const a = e.target.closest && e.target.closest(".sheetlink");
    if (!a)
        return;
    e.preventDefault();
    const d = docByFile(a.dataset.sheet);
    if (d)
        openDoc(d);
});
function applyProjNet() {
    if (!PROJ_NET || !S)
        return;
    if (isSch()) {
        const i = S.nets.findIndex(n => (n.project || n.name) === PROJ_NET);
        if (i >= 0)
            selectNet(i, false, true);
    }
    else if (S.nets && !S.kind) {
        const i = S.nets.indexOf(PROJ_NET);
        if (i >= 0) {
            st.selNet = i;
            st.selComp = -1;
            inspect(() => netModel(i));
            draw();
        }
    }
}
function selectNet(ni, zoom, quiet) {
    SCH.sel = -1;
    SCH.selComp = -1;
    SCH.selNet = ni;
    const n = S.nets[ni];
    inspect(() => schNetModel(ni));
    if (!quiet)
        shareNet(n.project || n.name);
    const b = netBox(ni);
    if (zoom && b)
        fit([b[0] - 8, b[1] - 8, b[2] + 8, b[3] + 8]);
    else
        draw();
    buildNav();
}
function selectComp(ci, zoom) {
    const oi = S.objects.findIndex(o => o.k === "comp" && o.comp === ci);
    schSelect(oi);
    const b = S.comps[ci].b;
    if (zoom && b)
        fit([b[0] - 12, b[1] - 12, b[2] + 12, b[3] + 12]);
}
// ---- panels/navigator.tsx
// The Navigator of a sheet (c0177), a Preact component (change c0304): its parts and its nets, filtered; a click
// selects and frames one.
// keys: a part row is never reused for a net row (no title left behind)
function NavigatorPanel({ comps, nets }) {
    return preact.h(preact.Fragment, null,
        preact.h("div", { key: "hc", class: "navg" }, `Components (${comps.length})`),
        comps.map(([c, i]) => preact.h("div", { key: "c:" + i, class: "navi" + (SCH.selComp === i ? " sel" : ""), title: c.description || c.lib || "", onClick: () => selectComp(i, true) },
            `${c.ref} `,
            preact.h("small", null, String(c.comment || c.lib || "")))),
        preact.h("div", { key: "hn", class: "navg" }, `Nets (${nets.length})`),
        nets.map(([n, i]) => preact.h("div", { key: "n:" + i, class: "navi" + (SCH.selNet === i ? " sel" : ""), onClick: () => selectNet(i, true) },
            String(n.name),
            n.project && n.project !== n.name ? " " : null,
            n.project && n.project !== n.name ? preact.h("small", null, `→ ${n.project}`) : null,
            " ",
            preact.h("small", null, `${n.pins.length}${n.sheets && n.sheets.length > 1 ? ` · ${n.sheets.length} sheets` : ""}`))));
}
function buildNav() {
    const box = $("navList");
    if (!box || !isSch())
        return;
    const q = SCH.filter.trim().toLowerCase();
    const comps = S.comps.map((c, i) => [c, i]).filter(([c]) => !c.hidden).filter(([c]) => !q || c.ref.toLowerCase().includes(q) || (c.comment || "").toLowerCase().includes(q)).sort((a, b) => natural(a[0].ref, b[0].ref));
    const nets = S.nets.map((n, i) => [n, i]).filter(([n]) => n.name && (n.pins.length > 1 || !n.name.startsWith("Net")) && (!q || n.name.toLowerCase().includes(q))).sort((a, b) => natural(a[0].name, b[0].name));
    preact.render(preact.h(NavigatorPanel, { comps: comps, nets: nets }), box);
}
$("navFilter").addEventListener("input", e => { SCH.filter = e.target.value; buildNav(); });
// ---- sch/load.ts
function sheetTabs() {
    const box = $("tablist");
    box.innerHTML = "";
    const docs = allDocs().filter(d => d.viewable && d.present).sort((a, b) => (a.kind !== "schematic") - (b.kind !== "schematic") || natural(a.name, b.name));
    for (const d of docs) {
        const t = document.createElement("div");
        t.className = "tab doc-tab" + (DOC && DOC.id === d.id ? " cur" : "");
        t.style.borderBottomColor = DOC && DOC.id === d.id ? (KIND_COLOR[d.kind] || "#888") : "transparent";
        t.innerHTML = `<span class="sw" style="background:${KIND_COLOR[d.kind] || "#888"}"></span><span>${esc(d.name)}</span>`;
        t.title = d.path;
        t.onclick = () => openDoc(d);
        box.appendChild(t);
    }
    $("cur").textContent = S ? `Sheet ${S.sheet.style} · ${S.comps.length} parts · ${S.nets.filter(n => n.name).length} nets` : "";
}
async function crossProbe(ref, kind) {
    const want = ref.toLowerCase(), generation = navigation;
    for (const d of allDocs().filter(x => x.kind === kind && x.viewable && x.present)) {
        let sc = null;
        try {
            sc = await sceneOf(d);
        }
        catch (e) {
            if (generation !== navigation)
                return false;
            continue;
        }
        if (generation !== navigation)
            return false;
        if (!sc)
            continue;
        const ok = sc.comps.some(c => c.ref.toLowerCase() === want || (c.group || "").toLowerCase() === want);
        if (ok) {
            const shown = await openDoc(d);
            if (!shown || shown !== navigation)
                return false;
            find(ref);
            return true;
        }
    }
    showInfo(`No ${kind === "pcb" ? "board" : "schematic"} of this project holds <b>${esc(ref)}</b>.`);
    return false;
}
function schDouble(X, Y) {
    const oi = schPick(X, Y);
    if (oi < 0)
        return;
    const o = S.objects[oi];
    if (o.k === "sheet" && o.file) {
        const d = docByFile(o.file);
        if (d)
            openDoc(d);
        else
            showInfo(`The sheet <b>${esc(o.file)}</b> is not a viewable document of this project.`);
        return;
    }
    const ci = o.comp;
    if (ci >= 0) {
        const c = S.comps[ci];
        crossProbe(c.group || c.ref, "pcb");
    }
}
function schFind(q) {
    const ql = q.toLowerCase();
    let ci = S.comps.findIndex(c => c.ref.toLowerCase() === ql);
    if (ci < 0)
        ci = S.comps.findIndex(c => (c.group || "").toLowerCase() === ql);
    if (ci >= 0) {
        selectComp(ci, true);
        return;
    }
    const ni = S.nets.findIndex(n => n.name && n.name.toLowerCase() === ql);
    if (ni >= 0) {
        selectNet(ni, true);
        return;
    }
    showInfo(`Nothing named <b>${esc(q)}</b> on this sheet.`);
}
function loadSch(scene, keepView) {
    st.itemInfo = false;
    const first = S === null || S !== scene && !keepView;
    if (!scene.mm)
        toMMsch(scene);
    setS(scene);
    document.body.classList.add("sch");
    if (st.mode3d)
        set3D(false);
    SCH.sel = -1;
    SCH.selNet = -1;
    SCH.selComp = -1;
    showInfo(null);
    cv.style.display = "block";
    view.mirror = false;
    setDocTitle(S.meta.name);
    const c = S.meta.counts || {};
    $("ovTitle").style.display = "none";
    clearFindings();
    $("notes").innerHTML = (S.meta.notes || []).map(esc).join("<br>") + `<br>Read by the ${esc(S.meta.backend)} backend, evidence ${esc(S.meta.evidence)}.` +
        (c.kinds ? `<br>${c.items || 0} items: ${Object.entries(c.kinds).map(([k, n]) => `${n} ${esc(k)}`).join(" · ")}` // a Draftsman sheet (c0180)
            : `<br>${c.components || 0} parts · ${c.pins || 0} pins · ${c.wires || 0} wires · ${c.nets || 0} nets · ${c.power_ports || 0} power ports · ${c.ports || 0} ports`);
    sheetTabs();
    buildNav();
    buildDiffList();
    buildMessages();
    buildVariants();
    applyProjNet();
    if (first) {
        setFitted(false);
        fit();
    }
    else
        draw();
}
// ---- library/library.tsx
// ================================================================== libraries (c0179): the item list, each item drawn as a board or a sheet
let LIB = null, LIBSEL = -1, LIBQ = "";
function setLib(v) { LIB = v; }
function toUnits(sc) {
    if (sc.kind === "table")
        return sc; // c0190: a BOM document or an output job
    if (sc.kind === "library") {
        for (const it of sc.items)
            if (it.scene)
                toUnits(it.scene);
        return sc;
    }
    return sc.kind === "schematic" ? toMMsch(sc) : toMM(sc);
}
function itemNote(it) {
    if (it.copper_nm) {
        const b = it.copper_nm;
        return `${it.pads} pads · ${fmtPair((b[2] - b[0]) / 1e6, (b[3] - b[1]) / 1e6)}`;
    }
    return it.pins != null ? `${it.pins} pins` : "";
}
// The item list, a Preact component (c0300); its rows stay the direct children of #libList (the catalog tests count
// them), the empty line sits after it.
function LibList({ items }) {
    return preact.h(preact.Fragment, null, items.map(([it, i]) => preact.h("div", { key: i, class: "navi" + (i === LIBSEL ? " sel" : ""), title: it.description || it.name, onClick: () => openItem(i) },
        it.name,
        " ",
        preact.h("small", null, itemNote(it)))));
}
function buildLibList() {
    const box = $("libList");
    if (!LIB) {
        preact.render(null, box);
        return;
    }
    const q = LIBQ.trim().toLowerCase();
    const what = LIB.lib === "pcb" ? "Footprints" : LIB.lib === "drawing" ? "Sheets" : "Symbols";
    showSection("library", true, LIB.items.length, what);
    const items = LIB.items.map((it, i) => [it, i]).filter(([it]) => !q || it.name.toLowerCase().includes(q) || (it.description || "").toLowerCase().includes(q));
    preact.render(preact.h(LibList, { items: items }), box);
    let empty = $("libEmpty");
    if (!empty) {
        empty = document.createElement("div");
        empty.id = "libEmpty";
        box.after(empty);
    }
    preact.render(items.length ? null : preact.h(Empty, { text: LIB.items.length ? `No ${what.toLowerCase()} match “${LIBQ.trim()}”.` : "This library holds no item." }), empty);
}
function itemModel(it) {
    const rows = [...it.info];
    if (it.copper_nm) {
        const b = it.copper_nm;
        rows.push(["Copper extent", fmtPair((b[2] - b[0]) / 1e6, (b[3] - b[1]) / 1e6)]);
    }
    if (it.courtyard_nm) {
        const b = it.courtyard_nm;
        rows.push(["Courtyard", fmtPair((b[2] - b[0]) / 1e6, (b[3] - b[1]) / 1e6)]);
    }
    const kind = LIB.lib === "pcb" ? "Footprint" : LIB.lib === "drawing" ? "Sheet" : "Symbol";
    return imodel(kind.toLowerCase(), it.name, [isection(it.lib_id ? `${kind} · ${it.evidence || "INFERRED"}` : kind, rows.map(([k, v]) => irow(k, v)), { collapsed: !!it.lib_id })], { subtitle: [LIB.meta.name, itemNote(it)].filter(Boolean).join(" · ") });
}
function itemInfo(it) {
    const rows = [...it.info];
    if (it.copper_nm) {
        const b = it.copper_nm;
        rows.push(["Copper extent", fmtPair((b[2] - b[0]) / 1e6, (b[3] - b[1]) / 1e6)]);
    }
    if (it.courtyard_nm) {
        const b = it.courtyard_nm;
        rows.push(["Courtyard", fmtPair((b[2] - b[0]) / 1e6, (b[3] - b[1]) / 1e6)]);
    }
    const title = `<b>Properties</b> · ${LIB.lib === "pcb" ? "Footprint" : LIB.lib === "drawing" ? "Sheet" : "Symbol"}`;
    const table = rows.length ? `<table>${rows.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join("")}</table>` : "";
    return it.lib_id ? `<details><summary>${title} · ${esc(it.evidence || "INFERRED")}</summary>${table}</details>` : title + table;
}
function openItem(i, keepView) {
    LIBSEL = i;
    const it = LIB.items[i];
    buildLibList();
    if (!it.scene) {
        showInfo(`<b>${esc(it.name)}</b> could not be drawn; see the notes.`);
        return;
    }
    if (it.scene.kind === "schematic")
        loadSch(it.scene, keepView);
    else
        loadBoard(it.scene, keepView);
    document.body.classList.add("lib");
    setDocTitle(`${LIB.meta.name} › ${it.name}`, LIB.meta.name);
    inspectQuiet(() => itemModel(it));
    st.itemInfo = true;
    refreshSummary();
    refreshDock(); // opening an item opens no bottom sheet
}
function loadLibrary(scene, keepView) {
    const prev = LIB && LIBSEL >= 0 ? LIB.items[LIBSEL].name : null;
    LIB = scene;
    document.body.classList.add("lib");
    let i = prev ? scene.items.findIndex(it => it.name === prev) : -1;
    if (i < 0)
        i = scene.items.findIndex(it => it.scene);
    if (i < 0)
        i = 0;
    if (!scene.items.length) {
        LIBSEL = -1;
        buildLibList();
        showInfo("This library holds no item.");
        return;
    }
    openItem(i, keepView && prev !== null);
    if (scene.meta.notes && scene.meta.notes.length)
        $("notes").innerHTML += "<br>" + scene.meta.notes.map(esc).join("<br>");
}
$("libFilter").addEventListener("input", e => { LIBQ = e.target.value; buildLibList(); });
// ---- inspect/model.ts
// ================================================================== the inspector model (c0301, design decision 2)
// What a click hits, as data: {kind, title, subtitle, sections: [{title, rows: [{label, value, copy}]}], target}.
// panels/inspector renders it in the dock. The builders between the markers are pure (the formatters come in as
// arguments) and run under Node in tests/unit/view/test_page.py -k inspector; a value the scene does not hold
// is left out, never shown as 0.
// ---- inspector model (c0301)
function irow(label, value, extra) {
    if (value === undefined || value === null || value === "" || (typeof value === "number" && !Number.isFinite(value)))
        return null;
    return { label: String(label), value: String(value), copy: true, ...(extra || {}) };
}
function isection(title, rows, extra) { const kept = rows.filter(Boolean); return kept.length ? { title, rows: kept, ...(extra || {}) } : null; }
function imodel(kind, title, sections, extra) { return { kind, title, sections: sections.filter(Boolean), ...(extra || {}) }; }
function modelText(m) {
    return [m.title, ...m.sections.map(s => [s.title, ...s.rows.map(r => `${r.label}: ${r.value}`)].join("\n"))].filter(Boolean).join("\n\n");
}
function padSection(p, f, layerOf) {
    const hasSize = p.w != null && p.h != null;
    return isection("Pad", [
        irow("Number", p.number), irow("Shape", p.shape), irow("Mounting", p.kind),
        hasSize ? irow("Size", f.pair(p.w / 1e6, p.h / 1e6)) : null,
        p.ratio != null && hasSize ? irow("Corner radius", f.nm(p.ratio / 1e6 * Math.min(p.w, p.h))) : null,
        p.drill != null ? irow("Drill", `Ø ${f.nm(p.drill)}`) : null,
        p.drill != null && p.slot ? irow("Slot length", f.nm(p.slot + p.drill)) : null,
        p.x != null && p.y != null ? irow("Centre", f.xy(p.x, p.y)) : null,
        p.rot != null ? irow("Rotation", `${(+p.rot).toFixed(1)}°`) : null,
        p.layers && p.layers.length ? irow("Layers", p.layers.map(layerOf).join(", ")) : null,
        p.mask != null ? irow("Mask expansion", f.nm(p.mask), { note: p.mask_src }) : null,
        p.mask != null && hasSize ? irow("Mask opening", f.pair(Math.max(p.w + 2 * p.mask, 0) / 1e6, Math.max(p.h + 2 * p.mask, 0) / 1e6)) : null,
        p.paste != null ? irow("Paste expansion", f.nm(p.paste), { note: p.paste_src }) : null,
    ]);
}
function trackSection(d, layer, f) {
    return isection("Track", [irow("Width", f.len(d[4])), irow("Length", f.len(Math.hypot(d[2] - d[0], d[3] - d[1]))), irow("Layer", layer),
        irow("Start", f.xy(d[0], d[1])), irow("End", f.xy(d[2], d[3]))]);
}
function arcSection(d, a, layer, f) {
    let span = null;
    if (a) {
        const T = 2 * Math.PI;
        span = ((a.a3 - a.a1) % T + T) % T;
        if (a.ccw)
            span = T - span;
    }
    return isection("Arc", [irow("Width", f.len(d[6])), a ? irow("Radius", f.len(a.r)) : null,
        span !== null ? irow("Angle", `${(span * 180 / Math.PI).toFixed(1)}°`) : null, span !== null ? irow("Length", f.len(a.r * span)) : null, irow("Layer", layer)]);
}
function viaSection(diameter, drill, layers, tented, f) {
    return isection("Via", [irow("Diameter", diameter != null ? f.len(diameter) : null), irow("Drill", drill != null ? `Ø ${f.len(drill)}` : null),
        irow("Layers", layers.join(", ")), irow("Mask", tented)]);
}
function zoneSection(label, layer, area, unfilled, f) {
    return isection("Zone", [irow("Name", label), irow("Layer", layer), unfilled ? irow("Fill", "not filled in the file") : null,
        area != null ? irow("Filled area", f.area(area)) : null]);
}
function netSection(name, info, layers, f) {
    return isection("Net", [irow("Name", name), info ? irow("Pads", info.pads) : null, info ? irow("Routed length", f.len(info.length)) : null,
        layers && layers.length ? irow("Layers", layers.join(", ")) : null]);
}
function partSection(c, variant, params, f) {
    const b = c.bbox;
    return isection("Part", [irow("Reference", c.ref), irow("Value", c.value), irow("Footprint", c.footprint), irow("Side", c.side),
        c.x != null && c.y != null ? irow("Position", f.xy(c.x, c.y)) : null, c.rotation != null ? irow("Rotation", `${c.rotation}°`) : null,
        b ? irow("Extent", f.pair(b[2] - b[0], b[3] - b[1])) : null, variant ? irow(`Variant ${variant[0]}`, variant[1]) : null,
        ...params.map(([k, v]) => irow(k, v, /^https?:\/\//i.test(String(v)) ? { link: String(v) } : undefined))]);
}
function keepoutSection(label, layer) {
    const m = /^(keep-out|rule area) (.*?)(?:: (.*))?$/.exec(String(label));
    return isection("Keep-out", [irow("Name", m ? m[2] : label), irow("Forbids", m && m[3] ? m[3] : null), irow("Layer", layer)]);
}
function findingSection(x, layer) {
    return isection("Finding", [irow("Code", x.code), irow("Severity", x.severity), irow("Stage", x.stage), irow("Evidence", x.evidence),
        irow("Message", x.message), irow("Where", x.where), irow("Layer", layer), irow("Guidance", x.hint), x.at ? null : irow("Position", "none on this document")]);
}
function areaOf(ring) {
    let s = 0;
    for (let i = 0, j = ring.length - 2; i < ring.length; j = i, i += 2)
        s += (ring[j] + ring[i]) * (ring[j + 1] - ring[i + 1]);
    return Math.abs(s) / 2;
}
// ---- end inspector model
const FMT = { len: v => fmtLen(v), nm: v => fmtNm(v), pair: (a, b) => fmtPair(a, b), xy: (a, b) => fmtXY(a, b), area: mm2 => fmtArea(mm2) };
function fmtArea(mm2) { return UNIT === "mil" ? `${(mm2 / (MIL_MM * MIL_MM)).toFixed(0)} mil²` : `${mm2.toFixed(3)} mm²`; }
function partParams(c) {
    const vs = variantOf(c.ref), params = { ...(c.params || {}), ...((vs && vs.params) || {}) };
    return Object.entries(params).map(([k, v]) => { const mil = /^(-?\d+(?:\.\d+)?)mil$/.exec(String(v)); return [k, mil ? fmtLen(+mil[1] * MIL_MM) : String(v)]; });
}
function boardPart(ci) { const c = S.comps[ci], vs = variantOf(c.ref); return partSection(c, vs ? [VARIANT, vs.kind] : null, partParams(c), FMT); }
function netLayers(ni) { const ids = new Set(); for (const pr of S.prims)
    if (pr[3] === ni && !pr[0].startsWith("View."))
        ids.add(pr[0]); return [...ids].map(layerName); }
function boardNet(ni) { const info = (S.netinfo || [])[ni]; return netSection(S.nets[ni], info ? { pads: info.pads, length: info.length * MM } : null, netLayers(ni), FMT); }
function boardModel(h, at) {
    const pr = h.pr, net = pr[3], ci = pr[4], label = pr[5] || "", lname = h.layer.name, sections = [];
    const pad = label && at ? padOf(label, at[0], at[1]) : null;
    let kind = "item", title = label || lname;
    if (pad) {
        kind = "pad";
        title = `${ci >= 0 ? S.comps[ci].ref : ""} · pad ${pad.number}`;
        sections.push(padSection(pad, FMT, layerName));
    }
    else if (pr[1] === "s") {
        kind = "track";
        title = label || "Track";
        sections.push(trackSection(pr[2], lname, FMT));
    }
    else if (pr[1] === "a") {
        kind = "arc";
        title = label || "Arc";
        sections.push(arcSection(pr[2], pr[6], lname, FMT));
    }
    else if (pr[1] === "c" && /^via \d+/.test(label)) {
        kind = "via";
        const base = label.replace(/ hole$/, ""), same = S.prims.filter(q => q[5] === base && q[1] === "c");
        const hole = S.prims.find(q => q[5] === base + " hole"), copper = same.filter(q => !/Mask$/.test(q[0]));
        const open = same.filter(q => /Mask$/.test(q[0])).map(q => layerName(q[0]));
        sections.push(viaSection(copper.length ? 2 * copper[0][2][2] : null, hole ? 2 * hole[2][2] : null, copper.map(q => layerName(q[0])), open.length ? `open on ${open.join(", ")}` : "tented or not stated", FMT));
        title = base.replace(/^via/, "Via");
    }
    else if (pr[1] === "c" && h.layer.id === "View.Drill") {
        kind = "hole";
        sections.push(isection("Hole", [irow("Diameter", `Ø ${fmtLen(2 * pr[2][2])}`), irow("Centre", FMT.xy(pr[2][0], pr[2][1]))]));
    }
    else if (pr[1] === "c")
        sections.push(isection("Circle", [irow("Diameter", fmtLen(2 * pr[2][2])), irow("Layer", lname)]));
    else if (pr[1] === "h" && /^(keep-out|rule area) /.test(label)) {
        kind = "keepout";
        title = "Keep-out";
        sections.push(keepoutSection(label, lname));
    }
    else if ((pr[1] === "p" || pr[1] === "o") && ci < 0 && net >= 0 || /\((no fill|outline)\)$/.test(label)) {
        kind = "zone";
        const name = label.replace(/ \((no fill|outline)\)$/, "");
        sections.push(zoneSection(name, lname, pr[1] === "p" ? pr[2].reduce((s, r) => s + areaOf(r), 0) : null, / \(no fill\)$/.test(label), FMT));
        title = name;
    }
    else
        sections.push(isection("Item", [irow("Name", label), irow("Layer", lname)]));
    if (kind !== "pad" && kind !== "zone" && kind !== "keepout" && kind !== "via" && sections[0] && !sections[0].rows.some(r => r.label === "Layer"))
        sections[0].rows.push(irow("Layer", lname));
    if (net >= 0)
        sections.push(boardNet(net), boardRole(net)); // c0305: the net's role after its Net section
    if (ci >= 0)
        sections.push(boardPart(ci));
    return imodel(kind, title, sections, { subtitle: lname, target: { pr, comp: ci, net, layer: h.layer.id } });
}
function partModel(ci) { const c = S.comps[ci]; return imodel("part", c.ref, [boardPart(ci)], { subtitle: [c.value, c.footprint].filter(Boolean).join(" · "), target: { comp: ci, net: -1 } }); }
function netModel(ni) { return imodel("net", S.nets[ni], [boardNet(ni), boardRole(ni)], { subtitle: "Net", target: { comp: -1, net: ni } }); }
function noteModel(title, text, extra) { return imodel("note", title, [], { note: text, ...(extra || {}) }); }
// ---- panels/inspector.tsx
// ================================================================== the inspector (c0301, design decisions 2 and 3)
// renderInspector(model) draws an inspector model of inspect/model in the dock's Properties tab (#info): a title,
// the actions that apply to the selection (registry commands, c0300), then one section per kind of value, each
// row with its copy control, and "Copy all". With nothing selected #info is empty and the document's summary
// (#infoEmpty) shows instead. A legacy HTML message still renders through showInfo(html).
const INSPECT = { model: null, waive: false };
const KIND_LABEL = { pad: "Pad", track: "Track", arc: "Arc", via: "Via", hole: "Hole", zone: "Zone", keepout: "Keep-out", part: "Part", net: "Net",
    finding: "Finding", item: "Item", body: "3D body", symbol: "Symbol", footprint: "Footprint", sheet: "Sheet", component: "Component", wire: "Wire",
    mark: "Review mark", measure: "Measurement", note: "" };
function Row({ r }) {
    const value = r.link ? preact.h("a", { href: r.link, target: "_blank", rel: "noopener noreferrer" }, r.value)
        : r.sheets ? preact.h(preact.Fragment, null, r.sheets.map((x, i) => preact.h(preact.Fragment, null,
            i ? ", " : "",
            preact.h("a", { href: "#", class: "sheetlink", "data-sheet": x }, x)))) : r.value;
    return preact.h("div", { class: "irow" },
        preact.h("span", { class: "ik" }, r.label),
        preact.h("span", { class: "iv" + (r.mono ? " mono" : "") },
            value,
            r.note ? preact.h("small", null, r.note) : null),
        r.copy ? preact.h("button", { type: "button", class: "tb icon small ghost icopy", "aria-label": `Copy ${r.label}`, "data-tip": `Copy ${r.label.toLowerCase()}`, onClick: () => copyAndSay(r.value, `${r.label} copied`) },
            preact.h(Icon, { name: "copy", size: 14 })) : null);
}
function WaiveForm() {
    const i = INSPECT.model.target.finding;
    const go = () => { const f = $("inspReason"), reason = f.value.trim(); if (!reason) {
        f.focus();
        return;
    } window.FenoliteActions.plan("waive", { finding: i, reason }); };
    return preact.h("div", { class: "waiveForm" },
        preact.h("label", { for: "inspReason" },
            "Reason for the waiver ",
            preact.h("small", null, "stored in the project file")),
        preact.h("input", { id: "inspReason", maxLength: 300, placeholder: "Accepted by design: \u2026", onKeyDown: e => { if (e.key === "Enter")
                go(); } }),
        preact.h("div", { class: "row" },
            preact.h("button", { type: "button", class: "tb small accentBtn", id: "inspWaivePlan", onClick: go },
                preact.h(Icon, { name: "waive", size: 14 }),
                preact.h("span", { class: "lbl" }, "Review plan\u2026")),
            preact.h("button", { type: "button", class: "tb small", onClick: () => { INSPECT.waive = false; refreshInspector(); } }, "Cancel")));
}
function StaleNote({ why }) {
    const again = DOC ? runAgainAction(DOC.id) : null;
    return preact.h("div", { class: "staleNote", id: "inspWaiveWhy", role: "status" },
        preact.h(Icon, { name: "alert", size: 14 }),
        preact.h("p", null, `Waive is not offered. ${why}`),
        again ? preact.h("button", { type: "button", id: "inspRunAgain", class: "tb small", disabled: !!RUNS.job, onClick: again.run },
            preact.h(Icon, { name: "refresh", size: 14 }),
            preact.h("span", { class: "lbl" }, again.label)) : null);
}
function InspectorActions() {
    const acts = COMMANDS.filter(c => c.group === "Selection" && available(c)), waive = waiveState();
    if (!acts.length && !waive.why)
        return null;
    return preact.h(preact.Fragment, null,
        preact.h("div", { class: "inspActs", role: "toolbar", "aria-label": "Actions on the selection" }, acts.map(c => preact.h("button", { type: "button", id: c.domId, class: "tb small act" + (c.tone ? " " + c.tone : ""), disabled: c.disabled && c.disabled(), "data-tip": c.tip ? c.tip() : c.title, "data-keys": c.keys.map(keyLabel).join(",") || undefined, onClick: () => runCommand(c.id) },
            preact.h(Icon, { name: c.icon, size: 14 }),
            preact.h("span", { class: "lbl" }, c.label ? c.label() : c.title)))),
        INSPECT.waive && waive.offered ? preact.h(WaiveForm, null) : null,
        waive.why ? preact.h(StaleNote, { why: waive.why }) : null);
}
function Inspector({ model }) {
    if (model.html)
        return preact.h("div", { class: "insp" },
            preact.h("div", { class: "ihtml", dangerouslySetInnerHTML: { __html: model.html } }));
    return preact.h("div", { class: "insp", "data-kind": model.kind },
        preact.h("header", { class: "inspHead" },
            preact.h("div", { class: "inspTitle" },
                KIND_LABEL[model.kind] ? preact.h("span", { class: "inspKind" }, KIND_LABEL[model.kind]) : null,
                preact.h("h2", { id: "inspTitle" }, model.title),
                model.subtitle ? preact.h("p", null, model.subtitle) : null),
            model.sections.length ? preact.h("button", { type: "button", id: "inspCopyAll", class: "tb small ghost", "data-tip": "Copy every row as text", onClick: () => copyAndSay(modelText(model), "Properties copied") },
                preact.h(Icon, { name: "copy", size: 14 }),
                preact.h("span", { class: "lbl" }, "Copy all")) : null),
        model.note ? preact.h("p", { class: "inspNote" }, model.note) : null,
        preact.h(InspectorActions, null),
        model.extra ? model.extra() : null,
        model.sections.map((s, k) => preact.h("details", { key: s.title + k, class: "isect", open: !s.collapsed },
            preact.h("summary", null,
                preact.h("span", { class: "chev" },
                    preact.h(Icon, { name: "chevRight", size: 12 })),
                s.title),
            preact.h("div", { class: "irows" }, s.rows.map(r => preact.h(Row, { r: r }))))));
}
function renderInspector(model) {
    INSPECT.model = model || null;
    preact.render(model ? preact.h(Inspector, { key: `${model.kind}:${model.title}`, model: model }) : null, $("info"));
}
function showModel(model) { INSPECT.waive = false; renderInspector(model); if (model)
    dockShowSelection(); }
function inspectQuiet(build) { const m = build(); if (m)
    m.rebuild = build; INSPECT.waive = false; renderInspector(m); }
function inspect(build) { const m = build(); if (m)
    m.rebuild = build; showModel(m); } // a model built again when the unit changes
function refreshInspector() {
    const m = INSPECT.model;
    if (!m)
        return;
    if (m.rebuild) {
        const again = m.rebuild();
        again.rebuild = m.rebuild;
        renderInspector(again);
    }
    else
        renderInspector(m);
}
// ---- the document's summary, shown while nothing is selected
function DocSummary() {
    if (!S || !DOC)
        return preact.h("div", { class: "docSum" },
            preact.h("p", { class: "hint" }, "No document is open."));
    const m = S.meta || {}, c = m.counts || {}, rows = [];
    const add = (k, v) => { if (v !== undefined && v !== null && v !== "")
        rows.push([k, String(v)]); };
    if (S.kind === "table") {
        add("Rows", S.rows.length);
        add("Columns", S.columns.length);
    }
    else if (LIB) {
        add("Items", LIB.items.length);
        add("Library", LIB.lib === "pcb" ? "footprints" : LIB.lib === "drawing" ? "sheets" : "symbols");
    }
    else if (isSch()) {
        add("Parts", c.components);
        add("Nets", c.nets);
        add("Wires", c.wires);
        add("Pins", c.pins);
        add("Sheet", S.sheet && S.sheet.style);
    }
    else {
        add("Parts", c.footprints);
        add("Pads", c.pads);
        add("Tracks", c.tracks);
        add("Vias", c.vias);
        add("Zones", c.zones);
        add("Layers", (S.layers || []).filter(l => l.kind !== "view").length);
    }
    add("Evidence", m.evidence);
    add("Notes", (m.notes || []).length || null);
    return preact.h("div", { class: "docSum" },
        preact.h("div", { class: "inspHead" },
            preact.h("div", { class: "inspTitle" },
                preact.h("span", { class: "inspKind" }, "Document"),
                preact.h("h2", null, DOC.name),
                preact.h("p", null, `${DOC.kind} · read by the ${m.backend || "?"} backend`))),
        preact.h("dl", { class: "sumGrid" }, rows.map(([k, v]) => preact.h("div", null,
            preact.h("dt", null, k),
            preact.h("dd", null, v)))),
        preact.h("p", { class: "hint" },
            preact.h(Icon, { name: "info", size: 14 }),
            S.kind === "table" ? "Click a row that names a document or parts to open it." : `Click ${isSch() ? "a part, a pin or a wire" : "a pad, a track, a via or a zone"} to see its properties here. Lengths read in ${UNIT === "mm" ? "millimetres" : "mil"} (Q).`));
}
function refreshSummary() { preact.render(preact.h(DocSummary, null), $("infoEmpty")); }
// ---- panels/layers.tsx
// ================================================================== the Layers panel (c0301, design decision 5)
// The dock's Layers tab, on boards and footprints: the layers of tabLayers() in groups (copper, mask and paste,
// silkscreen, mechanical and fabrication, view), each row with its swatch, its full name (wrapped, never cut),
// whether it is current, an opacity slider (l.alpha) and its visibility; a group's header shows or hides the
// group. The layer sets of #lsmenu are the presets, with "Current layer only" (Shift+S). Sheet tabs stay in the
// bottom bar.
const LAYER_GROUPS = [["copper", "Copper"], ["mask", "Mask and paste"], ["silk", "Silkscreen"], ["mech", "Mechanical and fabrication"], ["view", "View"]];
function layerGroup(l) {
    if (l.kind === "view" || l.id.startsWith("View."))
        return "view";
    if (l.kind === "copper" || /\.Cu$/.test(l.id))
        return "copper";
    if (/mask|paste/i.test(l.kind || "") || /\.(Mask|Paste)$/.test(l.id))
        return "mask";
    if (/silk/i.test(l.kind || "") || /\.SilkS$/.test(l.id))
        return "silk";
    return "mech";
}
function relayer() { buildLayers(); draw(); }
function setVisible(id, on) { vis.set(id, on); relayer(); }
function setGroup(ids, on) { for (const id of ids)
    vis.set(id, on); relayer(); }
function LayersPanel() {
    const layers = tabLayers(), by = new Map(LAYER_GROUPS.map(([g]) => [g, []]));
    for (const l of layers)
        by.get(layerGroup(l)).push(l);
    return preact.h(preact.Fragment, null,
        preact.h("div", { class: "layerTools" },
            preact.h("span", { class: "layerHint" }, st.single ? "Only the current layer is shown." : `${layers.filter(l => vis.get(l.id)).length} of ${layers.length} layers shown`)),
        LAYER_GROUPS.map(([g, title]) => {
            const list = by.get(g);
            if (!list.length)
                return null;
            const shown = list.filter(l => vis.get(l.id)).length;
            return preact.h("section", { class: "lgroup", key: g, "aria-label": title },
                preact.h("div", { class: "lgHead" },
                    preact.h("span", { class: "lgTitle" }, title),
                    preact.h("span", { class: "lgN" }, `${shown}/${list.length}`),
                    preact.h("button", { type: "button", class: "tb icon small ghost", "aria-pressed": shown > 0, "aria-label": `${shown ? "Hide" : "Show"} the ${title.toLowerCase()} layers`, "data-tip": `${shown ? "Hide" : "Show"} the group`, onClick: () => setGroup(list.map(l => l.id), !shown) },
                        preact.h(Icon, { name: shown ? "eye" : "eyeOff", size: 14 }))),
                list.map(l => {
                    const on = !!vis.get(l.id), cur = l.id === st.cur, pct = Math.round((l.alpha ?? 1) * 100);
                    return preact.h("div", { key: l.id, class: "lrow" + (cur ? " cur" : "") + (on ? "" : " off"), "data-layer": l.id },
                        preact.h("button", { type: "button", role: "radio", "aria-checked": cur, class: "lcur", "aria-label": `Make ${l.name} the current layer`, "data-tip": "Current layer", onClick: () => setCurrent(l.id) },
                            preact.h("span", { class: "radio" })),
                        preact.h("span", { class: "sw", style: `background:${l.color}` }),
                        preact.h("span", { class: "lname", title: l.name === l.id ? `${l.name} · ${l.kind}` : `${l.name} (${l.id}) · ${l.kind}`, onClick: () => setCurrent(l.id) }, l.name),
                        preact.h("input", { type: "range", class: "lop", min: "0", max: "100", step: "5", value: pct, "aria-label": `Opacity of ${l.name}`, title: `Opacity ${pct} %`, onInput: e => { l.alpha = +e.target.value / 100; draw(); e.target.title = `Opacity ${Math.round(l.alpha * 100)} %`; } }),
                        preact.h("button", { type: "button", class: "tb icon small ghost leye", "aria-pressed": on, "aria-label": `${on ? "Hide" : "Show"} ${l.name}`, "data-tip": on ? "Hide" : "Show", onClick: () => setVisible(l.id, !on) },
                            preact.h(Icon, { name: on ? "eye" : "eyeOff", size: 14 })));
                }));
        }),
        preact.h(RoleLayers, null));
}
function buildLayers() {
    const box = $("layerList");
    if (!box)
        return;
    if (!S || S.kind || !S.layers) {
        preact.render(null, box);
        return;
    }
    preact.render(preact.h(LayersPanel, null), box);
}
const presetNames = () => [...Object.keys(SETS), "Current layer only"];
// ---- panels/view3d-panel.tsx
// The 3D panel (c0301, design decision 6): the dock's tab in 3D instead of Layers: the camera views (the view
// cube's six faces and iso), what is drawn (bodies, board, silkscreen and copper textures) and Reset view.
const VIEWS = [["top", "Top"], ["front", "Front"], ["left", "Left"], ["iso", "Iso"], ["bottom", "Bottom"], ["back", "Back"], ["right", "Right"]];
const TOGGLES = [["bodies", "Bodies", "Parts: models, else outlines extruded to their height"], ["board", "Board", "The board slab and its edge"],
    ["silk", "Silkscreen", "The silkscreen of both faces"], ["copper", "Copper", "The copper of both faces"]];
function View3DPanel() {
    const bodies = (S && S.bodies) || [], models = bodies.filter(b => b.render === "model" || b.render === "fitted").length;
    return preact.h("div", { class: "p3d" },
        preact.h("section", { class: "lgroup" },
            preact.h("div", { class: "lgHead" },
                preact.h("span", { class: "lgTitle" }, "Camera")),
            preact.h("div", { class: "viewGrid" },
                VIEWS.map(([id, title]) => preact.h("button", { type: "button", id: `v3${id}`, class: "tb small", onClick: () => camPreset(id, true) }, title)),
                preact.h("button", { type: "button", id: "v3reset", class: "tb small", "data-tip": "The iso view, fitted to the board", onClick: () => camPreset("iso", true) },
                    preact.h(Icon, { name: "refresh", size: 14 }),
                    preact.h("span", { class: "lbl" }, "Reset"))),
            preact.h("p", { class: "hint" }, "Drag to orbit, Shift+drag to pan, wheel to zoom; the cube at the top right turns the view too.")),
        preact.h("section", { class: "lgroup" },
            preact.h("div", { class: "lgHead" },
                preact.h("span", { class: "lgTitle" }, "Show")),
            TOGGLES.map(([key, title, note]) => preact.h("label", { class: "tog", title: note },
                preact.h("input", { type: "checkbox", id: `c3${key}`, checked: !!V3[key], onChange: e => { set3DOption(key, e.target.checked); build3DPanel(); } }),
                preact.h("span", null, title),
                preact.h("small", null, note)))),
        preact.h("p", { class: "hint" }, bodies.length ? `${bodies.length} bodies: ${models} with a model, ${bodies.length - models} extruded.` : "No part body on this board."));
}
function build3DPanel() { preact.render(preact.h(View3DPanel, null), $("dock3d")); }
// ---- three/view-cube.ts
// ================================================================== the view cube (c0301, design decision 6)
// A 96-pixel cube at the top right of the 3D view, turned with the camera: its faces read Top, Bottom, Front,
// Back, Left and Right in Fenolite's stroke font; a click on a face sets that view, a click near a corner the iso
// view from that corner, both animated over 250 ms. A 2D canvas projection of the camera's axes, no WebGL.
const CUBE_FACES = [
    { n: [0, 0, 1], label: "TOP", view: "top" }, { n: [0, 0, -1], label: "BOTTOM", view: "bottom" },
    { n: [0, -1, 0], label: "FRONT", view: "front" }, { n: [0, 1, 0], label: "BACK", view: "back" },
    { n: [-1, 0, 0], label: "LEFT", view: "left" }, { n: [1, 0, 0], label: "RIGHT", view: "right" },
];
const cubeEl = $("cube");
let cubeHits = [], cubeTokens = null, cubeTheme = "";
function tokens() {
    const key = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: light)").matches ? "system-light" : "system-dark");
    if (cubeTokens && key === cubeTheme)
        return cubeTokens;
    const cs = getComputedStyle(document.documentElement), v = n => cs.getPropertyValue(n).trim();
    cubeTheme = key;
    cubeTokens = { face: v("--surface-2"), side: v("--surface-3"), edge: v("--border-strong"), text: v("--text-1"), dim: v("--text-3"), accent: v("--accent") };
    return cubeTokens;
}
function drawCube() {
    if (!cubeEl || cubeEl.style.display === "none")
        return;
    const dpr = window.devicePixelRatio || 1, size = 112, g = cubeEl.getContext("2d"), T = tokens();
    if (cubeEl.width !== size * dpr) {
        cubeEl.width = size * dpr;
        cubeEl.height = size * dpr;
    }
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, size, size);
    const [r, u, b] = camBasis(), s = 30, c = size / 2;
    const P = v => { const x = v[0] * r[0] + v[1] * r[1] + v[2] * r[2], y = v[0] * u[0] + v[1] * u[1] + v[2] * u[2], z = v[0] * b[0] + v[1] * b[1] + v[2] * b[2]; return [c + x * s, c - y * s, z]; };
    const faces = CUBE_FACES.map(f => {
        const n = f.n, axis = n.findIndex(x => x !== 0), o = [0, 1, 2].filter(k => k !== axis);
        const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([p, q]) => { const v = [0, 0, 0]; v[axis] = n[axis]; v[o[0]] = p; v[o[1]] = q; return P(v); });
        const facing = n[0] * b[0] + n[1] * b[1] + n[2] * b[2];
        return { ...f, corners, facing, center: P(n) };
    }).filter(f => f.facing > 0.02).sort((p, q) => p.facing - q.facing);
    cubeHits = [];
    for (const f of faces) {
        g.beginPath();
        f.corners.forEach(([x, y], i) => i ? g.lineTo(x, y) : g.moveTo(x, y));
        g.closePath();
        g.globalAlpha = 0.92;
        g.fillStyle = f.facing > 0.7 ? T.face : T.side;
        g.fill();
        g.globalAlpha = 1;
        g.strokeStyle = T.edge;
        g.lineWidth = 1;
        g.stroke();
        const xs = f.corners.map(p => p[0]), ys = f.corners.map(p => p[1]), fw = Math.max(...xs) - Math.min(...xs), fh = Math.max(...ys) - Math.min(...ys);
        const h = Math.min(9, 0.72 * fw / (f.label.length - 0.33), 0.5 * fh);
        if (f.facing > 0.3 && h >= 4.5) { // the label, in the stroke font, upright on screen, as wide as its face allows
            const lines = textPolylines(["", f.center[0], f.center[1], h, 0, 1, 0, "center", "center", false, f.label]);
            g.strokeStyle = f.facing > 0.7 ? T.text : T.dim;
            g.lineWidth = 1.2;
            g.lineCap = "round";
            g.lineJoin = "round";
            for (const pl of lines) {
                g.beginPath();
                pl.forEach(([x, y], i) => i ? g.lineTo(x, y) : g.moveTo(x, y));
                g.stroke();
            }
        }
        cubeHits.push({ kind: "face", view: f.view, poly: f.corners });
    }
    for (const sx of [-1, 1])
        for (const sy of [-1, 1])
            for (const sz of [-1, 1]) { // the corners in view: iso views
                const p = P([sx, sy, sz]);
                if (p[2] < -0.2)
                    continue;
                g.beginPath();
                g.arc(p[0], p[1], 2.5, 0, 2 * Math.PI);
                g.fillStyle = T.accent;
                g.fill();
                cubeHits.unshift({ kind: "corner", view: [Math.atan2(sy, sx), sz * 0.6155], at: p });
            }
}
function inPoly(x, y, poly) {
    let inside = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
        const [xi, yi] = poly[i], [xj, yj] = poly[j];
        if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi)
            inside = !inside;
    }
    return inside;
}
function cubeAt(x, y) {
    for (const h of cubeHits)
        if (h.kind === "corner" && Math.hypot(h.at[0] - x, h.at[1] - y) <= 7)
            return h;
    for (let i = cubeHits.length - 1; i >= 0; i--) {
        const h = cubeHits[i];
        if (h.kind === "face" && inPoly(x, y, h.poly))
            return h;
    }
    return null;
}
cubeEl.addEventListener("click", e => { const h = cubeAt(e.offsetX, e.offsetY); if (h)
    camPreset(h.view, true); });
cubeEl.addEventListener("mousemove", e => { cubeEl.style.cursor = cubeAt(e.offsetX, e.offsetY) ? "pointer" : "default"; });
const cubeFrame = () => V3.cam;
// ---- panels/dock.tsx
// ================================================================== the right dock (c0301, design decision 1)
// A third column of the page beside the drawing, never over it: the Properties tab (the inspector, #info) and,
// on boards and footprints, the Layers tab, which the 3D panel replaces in 3D. `I` collapses and opens it; its
// left edge resizes it between 240 and 480 px; both are kept in localStorage. At 760 px and below it is a bottom
// sheet of at most 60 % of the height that a selection opens and Esc or its close control dismisses.
const store = (key, fallback) => { try {
    return localStorage.getItem(key) ?? fallback;
}
catch (e) {
    return fallback;
} };
const keep = (key, value) => { try {
    localStorage.setItem(key, value);
}
catch (e) { /* kept for this page only */ } };
const DOCK = { open: store("fenolite.view.dock", "open") !== "closed", width: Math.min(480, Math.max(240, +store("fenolite.view.dockWidth", "320") || 320)),
    tab: "props", sheet: false };
const dockNarrow = () => matchMedia("(max-width:760px)").matches;
const layersApply = () => !!S && !S.kind && !isSch(); // a board or a footprint item
function DockHead() {
    const second = layersApply() ? (st.mode3d ? ["3d", "3D view", "cube"] : ["layers", "Layers", "layers"]) : null;
    const tabs = [["props", "Properties", "sliders"], ...(second ? [second] : [])];
    if (!tabs.some(t => t[0] === DOCK.tab))
        DOCK.tab = "props";
    return preact.h(preact.Fragment, null,
        preact.h("div", { class: "dockTabs", role: "tablist", "aria-label": "Inspector" }, tabs.map(([id, title, icon]) => preact.h("button", { type: "button", role: "tab", id: `dockTab_${id}`, "aria-selected": DOCK.tab === id, "aria-controls": id === "props" ? "dockProps" : id === "layers" ? "dockLayers" : "dock3d", class: "dockTab", onClick: () => setDockTab(id) },
            preact.h(Icon, { name: icon, size: 14 }),
            preact.h("span", null, title)))),
        preact.h("button", { type: "button", id: "dockClose", class: "tb icon small ghost", "aria-label": dockNarrow() ? "Close the inspector" : "Hide the inspector", "data-tip": dockNarrow() ? "Close" : "Hide the inspector", "data-keys": dockNarrow() ? "Esc" : "I", onClick: () => dockNarrow() ? closeSheet() : setDock(false) },
            preact.h(Icon, { name: dockNarrow() ? "x" : "dock", size: 14 })));
}
function refreshDock() {
    const app = $("app");
    app.classList.toggle("dock-closed", !DOCK.open);
    app.classList.toggle("dock-sheet-open", DOCK.sheet);
    app.style.setProperty("--dock-w", `${DOCK.width}px`);
    preact.render(preact.h(DockHead, null), $("dockHead"));
    $("dockProps").hidden = DOCK.tab !== "props";
    $("dockLayers").hidden = DOCK.tab !== "layers";
    $("dock3d").hidden = DOCK.tab !== "3d";
    if (DOCK.tab === "layers")
        buildLayers();
    else if (DOCK.tab === "3d")
        build3DPanel();
}
function setDockTab(id) { DOCK.tab = id; refreshDock(); }
function setDock(open) { DOCK.open = open; keep("fenolite.view.dock", open ? "open" : "closed"); refreshDock(); refreshToolbar(); }
function toggleDock() { if (dockNarrow()) {
    if (DOCK.sheet)
        closeSheet();
    else
        openSheet();
}
else
    setDock(!DOCK.open); }
function openSheet() { DOCK.sheet = true; refreshDock(); }
function closeSheet() { if (!DOCK.sheet)
    return false; DOCK.sheet = false; refreshDock(); return true; }
function dockShowSelection() {
    let changed = false;
    if (DOCK.tab !== "props") {
        DOCK.tab = "props";
        changed = true;
    }
    if (dockNarrow() && !DOCK.sheet) {
        DOCK.sheet = true;
        changed = true;
    }
    if (changed)
        refreshDock();
}
// The resize handle: a pointer drag on the dock's left edge, or the arrow keys on it.
function setWidth(w) { DOCK.width = Math.round(Math.min(480, Math.max(240, w))); $("app").style.setProperty("--dock-w", `${DOCK.width}px`); keep("fenolite.view.dockWidth", String(DOCK.width)); }
$("dockResize").addEventListener("pointerdown", (e) => {
    if (dockNarrow())
        return;
    e.preventDefault();
    const grip = e.currentTarget, x0 = e.clientX, w0 = DOCK.width;
    grip.setPointerCapture(e.pointerId);
    grip.classList.add("on");
    const move = (m) => setWidth(w0 + x0 - m.clientX);
    const up = () => { grip.classList.remove("on"); grip.removeEventListener("pointermove", move); grip.removeEventListener("pointerup", up); };
    grip.addEventListener("pointermove", move);
    grip.addEventListener("pointerup", up);
});
$("dockResize").addEventListener("keydown", (e) => {
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        setWidth(DOCK.width + (e.key === "ArrowLeft" ? 16 : -16));
    }
});
matchMedia("(max-width:760px)").addEventListener?.("change", () => { DOCK.sheet = false; refreshDock(); });
// ---- core/palette-match.ts
// ---- palette (c0300)
// The matcher of the command palette (design decision 4): case-insensitive; a label that starts with the query
// ranks first, then one where a word starts with it, then one that holds its letters in order (a subsequence);
// shorter labels first within a rank, then the order given. A leading ">" keeps commands, "@" parts and "#" nets.
// Pure functions, run under Node by tests/unit/view/test_page.py -k palette_match.
const PALETTE_LIMIT = 50;
const PALETTE_PREFIX = { ">": "command", "@": "part", "#": "net" };
function paletteScore(q, label) {
    const l = String(label || "").toLowerCase();
    if (!q)
        return 1;
    const len = Math.min(l.length, 999);
    if (l.startsWith(q))
        return 3000 - len;
    for (let i = 1; i < l.length; i++)
        if (!/[a-z0-9]/.test(l[i - 1]) && /[a-z0-9]/.test(l[i]) && l.startsWith(q, i))
            return 2000 - len;
    let j = 0;
    for (let i = 0; i < l.length && j < q.length; i++)
        if (l[i] === q[j])
            j++;
    return j === q.length ? 1000 - len : 0;
}
function paletteParse(query) {
    const t = String(query || "").trimStart(), kind = PALETTE_PREFIX[t[0]] || null;
    return { q: (kind ? t.slice(1) : t).trim().toLowerCase(), kind };
}
function paletteMatch(query, items) {
    const { q, kind } = paletteParse(query), scored = [];
    items.forEach((it, i) => {
        if (kind && it.kind !== kind)
            return;
        const s = Math.max(paletteScore(q, it.label), it.alt ? paletteScore(q, it.alt) - 500 : 0);
        if (s > 0)
            scored.push([s, i, it]);
    });
    scored.sort((a, b) => b[0] - a[0] || a[1] - b[1]);
    return scored.slice(0, PALETTE_LIMIT).map(x => x[2]);
}
// ---- end palette
// ---- core/commands.ts
// ================================================================== the command registry (c0300, design decision 2)
// Every action of the shell, declared once: the toolbar is built from it, the palette lists it, the shortcut sheet
// prints it, and the keydown listener of core/input looks its shortcuts up here. `when()` says whether a command
// applies to what is shown (board, sheet, library, table, 3D); `pressed()` gives a toggle's state. Later changes
// add their commands (c0301 to c0303).
let IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || ""); // let: a test sets it to check the macOS chord
const cad = () => !!S && S.kind !== "table";
const board = () => !!S && !S.kind && !isSch();
const board2d = () => board() && !st.mode3d;
const flat = () => cad() && !st.mode3d;
const narrow = () => matchMedia("(max-width:760px)").matches;
const sidebarOpen = () => $("app").classList.contains("sidebar-open");
function escapeKey() {
    if (narrow() && sidebarOpen()) {
        setSidebar(false);
        $("bSidebar").focus();
        return;
    }
    if (narrow() && closeSheet())
        return; // c0301: the inspector's bottom sheet
    if (!cad())
        return;
    if (st.edge) {
        toggleEdge();
        return;
    }
    if (st.marking) {
        toggle("marking");
        return;
    }
    if (st.measure || st.mpts.length) {
        st.mpts = [];
        st.mhover = null;
        if (st.measure)
            toggle("measure");
        else
            draw();
        return;
    }
    if (isSch()) {
        schSelect(-1);
        shareNet(null);
        return;
    }
    if (st.mode3d)
        return;
    st.mpts = [];
    st.selOv = -1;
    ROLE_SEL.group = -1;
    ROLE_SEL.finding = -1;
    select(null);
    shareNet(null);
}
const PRINT = [["fit", "Fit to the page"], ["1", "1:1"], ["2", "2:1"], ["5", "5:1"], ["10", "10:1"]];
// ---- the selection's actions (c0301, design decision 3; c0303): commands of the group "Selection" on the target of
// the inspector's model, shown in the inspector and listed in the palette.
const target = () => (INSPECT.model && INSPECT.model.target) || null;
const tComp = () => { const t = target(); return t && t.comp >= 0 ? t.comp : -1; };
const tNet = () => { const t = target(); return t && t.net >= 0 ? t.net : -1; };
const tFinding = () => { const t = target(); return t && t.finding != null && S.check && S.check.findings[t.finding] ? t.finding : -1; };
const kind = () => INSPECT.model ? INSPECT.model.kind : "";
function probeKind() { return isSch() ? "pcb" : "schematic"; }
function probeOffered() {
    const ci = tComp();
    if (ci < 0 || !S || !S.comps || LIB)
        return false;
    const c = S.comps[ci], want = String(c.group || c.ref).toLowerCase(), docs = allDocs().filter(d => d.kind === probeKind() && d.viewable && d.present);
    if (!docs.length)
        return false;
    const known = docs.map(d => SCENES.get(d.id)).filter(Boolean);
    return known.length < docs.length || known.some(sc => sc.comps.some(x => x.ref.toLowerCase() === want || String(x.group || "").toLowerCase() === want));
}
function zoomToTarget() {
    const t = target();
    if (!t || !S)
        return;
    const frame = (b, m) => { if (b)
        fit([b[0] - m, b[1] - m, b[2] + m, b[3] + m]); };
    if (st.mode3d)
        set3D(false);
    if (t.overlay != null) {
        gotoFinding(t.overlay);
        return;
    }
    if (t.finding != null && S.check) {
        const x = S.check.findings[t.finding];
        if (x.at) {
            const b = x.box || [x.at[0], x.at[1], x.at[0], x.at[1]];
            frame(b, Math.max(b[2] - b[0], b[3] - b[1], 6) * 0.8);
        }
        return;
    }
    if (isSch()) {
        if (t.comp >= 0)
            frame(S.comps[t.comp].b, 12);
        else if (t.net >= 0)
            frame(netBox(t.net), 8);
        return;
    }
    if (t.pr)
        frame(bboxOf(t.pr), 3);
    else if (t.comp >= 0)
        frame(S.comps[t.comp].bbox, 5);
    else if (t.net >= 0)
        frame(netBounds(t.net), 3);
}
function openInReview(i) {
    setProjectReview(true);
    const k = REVIEW.items.findIndex(x => x.checkIndex === i);
    if (k >= 0) {
        REVIEW.selected = k;
        filterReviewFindings();
    }
}
function moveInActions(ci) {
    st.selComp = ci;
    setProjectReview(true);
    const box = document.querySelector('#actionPanel details[data-action="move"]');
    if (!box)
        return;
    box.open = true;
    box.scrollIntoView({ block: "center" });
    box.querySelector('[data-opt="x"]')?.focus();
}
function waiveState() {
    const i = tFinding();
    if (i < 0)
        return { offered: false, why: "" };
    const x = S.check.findings[i], A = window.FenoliteActions && window.FenoliteActions.state;
    if (!A || !A.enabled || !A.offer?.waive?.available || x.stage !== "drc.kicad")
        return { offered: false, why: "" };
    const why = waiveBlocked();
    return { offered: !why, why };
}
// ---- commands (c0300)
const COMMANDS = [
    { id: "view.3d", title: "3D view", group: "View", icon: "cube", keys: ["D"], when: () => board(), run: () => set3D(!st.mode3d), pressed: () => st.mode3d },
    { id: "view.fit", title: "Fit to the window", group: "View", icon: "fit", keys: ["F"], when: () => cad(), run: () => st.mode3d ? camPreset("iso") : fit() },
    { id: "view.flip", title: "View from below", group: "View", icon: "flip", keys: ["B"], when: () => board2d(), run: () => flip(), pressed: () => view.mirror },
    { id: "view.zoomIn", title: "Zoom in", group: "View", icon: "zoom", keys: ["PageUp"], when: () => isSch(), run: () => zoomBy(1.25) },
    { id: "view.zoomOut", title: "Zoom out", group: "View", icon: "zoom", keys: ["PageDown"], when: () => isSch(), run: () => zoomBy(0.8) },
    { id: "view.single", title: "Current layer only", group: "Layers", icon: "layer", keys: ["Shift+S"], when: () => board2d(), run: () => { st.single = !st.single; buildTabs(); draw(); }, pressed: () => st.single },
    { id: "view.nextLayer", title: "Next layer", group: "Layers", icon: "arrowUp", keys: ["+", "="], when: () => board2d(), run: () => stepCurrent(1) },
    { id: "view.prevLayer", title: "Previous layer", group: "Layers", icon: "arrowDown", keys: ["-", "_"], when: () => board2d(), run: () => stepCurrent(-1) },
    { id: "view.changes", title: "Show or hide the changes", group: "View", icon: "changes", keys: ["X"], when: () => cad() && !!S.diff, run: () => { st.diff = !st.diff; draw(); }, pressed: () => st.diff },
    { id: "view.checks", title: "Show or hide the check markers", group: "View", icon: "target", keys: ["E"], when: () => cad() && !!S.check, run: () => { st.checks = !st.checks; draw(); }, pressed: () => st.checks },
    { id: "tools.edge", title: "Edge gap", group: "Tools", icon: "gap", keys: ["Shift+M"], when: () => board2d(), run: () => toggleEdge(), pressed: () => st.edge },
    { id: "tools.measure", title: "Measure", group: "Tools", icon: "ruler", keys: ["M"], when: () => flat(), run: () => toggle("measure"), pressed: () => st.measure },
    { id: "tools.mark", title: "Review mark", group: "Tools", icon: "pin", keys: ["N"], when: () => flat(), run: () => toggle("marking"), pressed: () => st.marking },
    { id: "tools.units", title: "Units: millimetres or mil", group: "Tools", icon: "units", keys: ["Q"], when: () => cad(), run: () => setUnit(UNIT === "mm" ? "mil" : "mm") },
    { id: "tools.similar", title: "Find similar", group: "Tools", icon: "similar", keys: [], when: () => board2d() && (st.selComp >= 0 || !!st.lastHit), run: () => findSimilar() },
    { id: "tools.clearFilter", title: "Clear the filter", group: "Tools", icon: "filter", keys: ["Shift+C"], when: () => board2d(), run: () => clearQuery() },
    { id: "tools.escape", title: "Clear the selection or leave the tool", group: "Tools", icon: "clear", keys: ["Escape"], when: () => true, run: () => escapeKey() },
    { id: "view.dock", title: "Inspector", group: "View", icon: "dock", keys: ["I"], when: () => !!S, run: () => toggleDock(), pressed: () => dockNarrow() ? DOCK.sheet : DOCK.open },
    { id: "insp.zoom", title: "Zoom to", group: "Selection", icon: "zoom", keys: [], domId: "inspZoom", when: () => !!target() && kind() !== "measure" && kind() !== "mark" && S.kind !== "table", run: () => zoomToTarget() },
    { id: "insp.net", title: "Highlight net", group: "Selection", icon: "net", keys: [], domId: "inspNet", when: () => tNet() >= 0 && kind() !== "net" && (!st.mode3d || isSch()),
        run: () => isSch() ? selectNet(tNet(), true) : selectNetAt(tNet()) },
    { id: "insp.part", title: "Select part", group: "Selection", icon: "chip", keys: [], domId: "inspPart", when: () => tComp() >= 0 && kind() !== "part" && kind() !== "component" && !LIB,
        run: () => isSch() ? selectComp(tComp(), true) : selectCompAt(tComp()) },
    { id: "insp.similar", title: "Find similar", group: "Selection", icon: "similar", keys: [], domId: "inspSimilar", when: () => board2d() && !LIB && (tComp() >= 0 || !!target()?.pr), run: () => findSimilar() },
    { id: "insp.probe", title: "Show in schematic", group: "Selection", icon: "schematic", keys: [], label: () => isSch() ? "Show on board" : "Show in schematic", domId: "inspProbe",
        when: () => probeOffered(), run: () => { const c = S.comps[tComp()]; crossProbe(c.group || c.ref, probeKind()); } },
    { id: "insp.review", title: "Open in review", group: "Selection", icon: "review", keys: [], domId: "inspReview", when: () => tFinding() >= 0, run: () => openInReview(tFinding()) },
    { id: "act.waive", title: "Waive finding…", group: "Selection", icon: "waive", keys: [], domId: "inspWaive", tone: "warnBtn", when: () => waiveState().offered,
        run: () => { INSPECT.waive = !INSPECT.waive; refreshInspector(); }, disabled: () => !!(window.FenoliteActions?.state?.job) },
    { id: "act.move", title: "Move part…", group: "Selection", icon: "move", keys: [], domId: "inspMove",
        when: () => tComp() >= 0 && board2d() && !LIB && !!window.FenoliteActions?.state?.enabled && !!window.FenoliteActions.state.offer?.move?.available, run: () => moveInActions(tComp()) },
    { id: "act.confirmRole", title: "Confirm role…", group: "Selection", icon: "check", keys: [], domId: "inspConfirmRole",
        when: () => tNet() >= 0 && board2d() && roleOfNet(tNet())?.state === "inferred" && confirmOffered(),
        run: () => confirmRoles([roleOfNet(tNet()).net], []), disabled: () => !!(window.FenoliteActions?.state?.job) },
    { id: "roles.colors", title: "Roles: colour the copper by role", group: "Roles", icon: "net", keys: [], when: () => board2d() && !!rolesData(),
        run: () => setRoleView("colors", !ROLE_VIEW.colors), pressed: () => !!ROLE_VIEW.colors },
    { id: "roles.loops", title: "Roles: hot and gate loops", group: "Roles", icon: "refresh", keys: [], when: () => board2d() && !!rolesData(),
        run: () => setRoleView("loops", !ROLE_VIEW.loops), pressed: () => !!ROLE_VIEW.loops },
    { id: "roles.kelvin", title: "Roles: Kelvin pairs", group: "Roles", icon: "gap", keys: [], when: () => board2d() && !!rolesData(),
        run: () => setRoleView("kelvin", !ROLE_VIEW.kelvin), pressed: () => !!ROLE_VIEW.kelvin },
    { id: "roles.findings", title: "Roles: role findings", group: "Roles", icon: "target", keys: [], when: () => board2d() && !!rolesData(),
        run: () => setRoleView("findings", !ROLE_VIEW.findings), pressed: () => !!ROLE_VIEW.findings },
    { id: "roles.run", title: "Roles: run fenolite roles --check", group: "Roles", icon: "play", keys: [], when: () => rolesRunOffered(),
        run: () => window.FenoliteRuns.start("roles", {}), disabled: () => !!RUNS.job },
    { id: "share.link", title: "Copy link", group: "Share", icon: "link", keys: [], when: () => !!DOC, run: () => copyLink() },
    { id: "share.svg", title: "Save as SVG", group: "Share", icon: "image", keys: [], when: () => flat(), run: () => saveSvg() },
    ...PRINT.map(([k, label]) => ({ id: `share.print.${k}`, title: `Print · ${label}`, group: "Share", icon: "printer", keys: [], when: () => flat(), run: () => printView(k) })),
    { id: "app.palette", title: "Search or run a command", group: "General", icon: "search", keys: ["Mod+K"], when: () => true, run: () => openPalette() },
    { id: "app.shortcuts", title: "Keyboard shortcuts", group: "General", icon: "keyboard", keys: ["?"], when: () => true, run: () => openShortcuts() },
    { id: "app.about", title: "About this document", group: "General", icon: "info", keys: [], when: () => !!DOC, run: () => openAbout() },
    { id: "app.review", title: "Project review", group: "General", icon: "review", keys: [], when: () => !!DOC, run: () => setProjectReview($("projectReview").hidden) },
    { id: "app.sidebar", title: "Show or hide the side bar", group: "General", icon: "sidebar", keys: [], when: () => narrow(), run: () => setSidebar(!sidebarOpen()), pressed: () => sidebarOpen() },
    { id: "app.run", title: "Run checks", group: "General", icon: "play", keys: [], when: () => RUNS.enabled && !!DOC && (DOC.viewable || DOC.kind === "project"),
        run: () => window.FenoliteRuns.start("check", {}), disabled: () => !!RUNS.job },
    { id: "app.theme.system", title: "Interface theme: follow the system", group: "General", icon: "monitor", keys: [], when: () => true, run: () => setTheme("system"), pressed: () => THEME === "system" },
    { id: "app.theme.dark", title: "Interface theme: dark", group: "General", icon: "moon", keys: [], when: () => true, run: () => setTheme("dark"), pressed: () => THEME === "dark" },
    { id: "app.theme.light", title: "Interface theme: light", group: "General", icon: "sun", keys: [], when: () => true, run: () => setTheme("light"), pressed: () => THEME === "light" },
];
// ---- end commands
const commandById = id => COMMANDS.find(c => c.id === id);
function available(c) { try {
    return !!c.when();
}
catch (e) {
    return false;
} }
function runCommand(id) {
    const c = commandById(id);
    if (!c || !available(c) || (c.disabled && c.disabled()))
        return false;
    c.run();
    refreshToolbar();
    return true;
}
const KEY_NAMES = { Escape: "Esc", PageUp: "PgUp", PageDown: "PgDn" };
function keyLabel(spec) {
    return spec === "+" ? "+" : spec.replace("Mod+", IS_MAC ? "⌘+" : "Ctrl+").split("+").map(k => KEY_NAMES[k] || k).join(" ");
}
function keyMatches(spec, e) {
    if (spec === "+" || spec === "-" || spec === "=" || spec === "_" || spec === "?")
        return e.key === spec;
    const parts = spec.split("+"), key = parts.pop(), mods = new Set(parts);
    if (mods.has("Mod"))
        return (IS_MAC ? e.metaKey : e.ctrlKey) && e.key.toLowerCase() === key.toLowerCase();
    if (key.length === 1 && /[a-z]/i.test(key))
        return e.key.toLowerCase() === key.toLowerCase() && e.shiftKey === mods.has("Shift");
    return e.key === key;
}
function commandForKey(e) {
    for (const c of COMMANDS)
        if (c.id !== "app.palette" && c.keys.some(k => keyMatches(k, e)) && available(c))
            return c;
    return null;
}
// ---- dialogs/palette.tsx
// ================================================================== the command palette (c0300, design decision 4)
// Ctrl+K (Cmd+K on macOS), or typing in the toolbar's search field: one field that runs a command of the registry
// or jumps to a part, a net, a document or a library item. Results come grouped by source, the best group first;
// arrows move, Enter runs or jumps (through the page's own selection functions and the navigation guard of
// openDoc), Esc closes and gives the focus back. ">" keeps commands, "@" parts, "#" nets.
const GROUPS = { command: "Commands", part: "Parts", net: "Nets", doc: "Documents", item: "Library" };
const KIND_ICON = { part: "chip", net: "net", doc: "doc", item: "chip" };
const PAL = { query: "", active: 0, items: [], results: [], back: null };
function paletteItems() {
    const out = [];
    for (const c of COMMANDS)
        if (available(c) && c.id !== "app.palette" && c.id !== "tools.escape")
            out.push({ kind: "command", label: c.title, alt: c.group, icon: c.icon, keys: c.keys.filter(k => k !== "=" && k !== "_").map(keyLabel), run: () => runCommand(c.id), disabled: c.disabled && c.disabled() });
    if (S && S.comps && S.kind !== "table") {
        const sch = isSch();
        const byRef = S.comps.map((c, i) => [c, i]).sort((a, b) => natural(a[0].ref, b[0].ref));
        for (const [c, i] of byRef) {
            if (c.hidden)
                continue;
            const sub = sch ? [c.comment, c.lib].filter(Boolean).join(" · ") : [c.value, c.footprint, c.side === "bottom" ? "bottom" : ""].filter(Boolean).join(" · ");
            out.push({ kind: "part", label: c.ref, alt: sch ? c.comment : c.value, sub, run: () => sch ? selectComp(i, true) : selectCompAt(i) });
        }
        if (sch)
            S.nets.forEach((n, i) => { if (n.name)
                out.push({ kind: "net", label: n.name, sub: `${n.pins.length} pins`, run: () => selectNet(i, true) }); });
        else
            S.nets.forEach((n, i) => {
                if (!n)
                    return;
                const info = (S.netinfo || [])[i];
                out.push({ kind: "net", label: n, sub: info ? `${info.pads} pads · ${fmtLen(info.length * MM)}` : "", run: () => selectNetAt(i) });
            });
    }
    if (LIB)
        LIB.items.forEach((it, i) => out.push({ kind: "item", label: it.name, sub: it.description || "", run: () => openItem(i) }));
    for (const d of allDocs())
        if (d.viewable && d.present)
            out.push({ kind: "doc", label: d.name, sub: d.path, color: KIND_COLOR[d.kind] || KIND_COLOR.other, current: DOC && DOC.id === d.id, run: () => openDoc(d) });
    return out;
}
function grouped(results) {
    const order = [], by = new Map();
    for (const r of results) {
        if (!by.has(r.kind)) {
            by.set(r.kind, []);
            order.push(r.kind);
        }
        by.get(r.kind).push(r);
    }
    return order.map(k => [k, by.get(k)]);
}
function refine() {
    const { q, kind } = paletteParse(PAL.query);
    let pool = PAL.items;
    if (!q && !kind)
        pool = pool.filter(it => it.kind === "command" || it.kind === "doc"); // nothing typed: what to do, where to go
    PAL.results = grouped(paletteMatch(PAL.query, pool)).flatMap(g => g[1]);
    PAL.active = Math.min(PAL.active, Math.max(PAL.results.length - 1, 0));
}
function Palette() {
    const groups = grouped(PAL.results), { kind } = paletteParse(PAL.query);
    let n = -1;
    return preact.h("div", { class: "palBox" },
        preact.h("div", { class: "palField" },
            preact.h(Icon, { name: "search" }),
            preact.h("input", { id: "palInput", role: "combobox", "aria-expanded": "true", "aria-controls": "palList", "aria-autocomplete": "list", "aria-activedescendant": PAL.results.length ? `pal${PAL.active}` : undefined, placeholder: "Search parts, nets and documents, or run a command\u2026", value: PAL.query, autocomplete: "off", spellcheck: false, onInput: e => { PAL.query = e.target.value; PAL.active = 0; refine(); renderPalette(); }, onKeyDown: paletteKey }),
            preact.h("kbd", null, "Esc")),
        preact.h("div", { id: "palList", role: "listbox", "aria-label": "Results" }, PAL.results.length ? groups.map(([k, list]) => preact.h("div", { role: "group", "aria-label": GROUPS[k], key: k },
            preact.h("div", { class: "palGroup" }, GROUPS[k]),
            list.map(r => {
                n++;
                const i = n;
                return preact.h("div", { id: `pal${i}`, key: i, role: "option", "aria-selected": Boolean(i === PAL.active), "aria-disabled": r.disabled ? true : undefined, class: "palItem" + (i === PAL.active ? " active" : ""), onMouseMove: () => { if (PAL.active !== i) {
                        PAL.active = i;
                        renderPalette();
                    } }, onClick: () => choose(i) },
                    preact.h("span", { class: "palIc" }, r.color ? preact.h("span", { class: "dot", style: `background:${r.color}` }) : preact.h(Icon, { name: r.icon || KIND_ICON[r.kind] })),
                    preact.h("span", { class: "palText" },
                        preact.h("span", { class: "palLabel" }, r.label),
                        r.sub ? preact.h("small", null, r.sub) : null),
                    r.current ? preact.h("span", { class: "palTag" }, "Open") : null,
                    (r.keys || []).map(k => preact.h("kbd", null, k)));
            }))) : preact.h("div", { class: "palEmpty" }, PAL.query.trim() ? `Nothing matches “${PAL.query.trim()}”` + (kind ? ` among ${GROUPS[kind].toLowerCase()}.` : ".") : "Type to search.")),
        preact.h("div", { class: "palFoot" },
            preact.h("span", null,
                preact.h("kbd", null, "\u2191"),
                preact.h("kbd", null, "\u2193"),
                " move"),
            preact.h("span", null,
                preact.h("kbd", null, "Enter"),
                " open or run"),
            preact.h("span", null,
                preact.h("kbd", null, ">"),
                " commands"),
            preact.h("span", null,
                preact.h("kbd", null, "@"),
                " parts"),
            preact.h("span", null,
                preact.h("kbd", null, "#"),
                " nets")));
}
function paletteKey(e) {
    const n = PAL.results.length;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (!n)
            return;
        PAL.active = (PAL.active + (e.key === "ArrowDown" ? 1 : -1) + n) % n;
        renderPalette();
        scrollActive();
    }
    else if (e.key === "Enter" && !e.isComposing) {
        e.preventDefault();
        choose(PAL.active);
    }
    else if ((e.key === "k" || e.key === "K") && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        closePalette(true);
    }
}
function scrollActive() { document.getElementById(`pal${PAL.active}`)?.scrollIntoView({ block: "nearest" }); }
function choose(i) {
    const r = PAL.results[i];
    if (!r || r.disabled)
        return;
    closePalette(false);
    document.activeElement?.blur?.();
    r.run();
}
function renderPalette() { preact.render(preact.h(Palette, null), $("palette")); }
function openPalette(query = "") {
    const dlg = $("palette");
    if (dlg.open) {
        PAL.query = query || PAL.query;
        refine();
        renderPalette();
        $("palInput").focus();
        return;
    }
    PAL.back = document.activeElement;
    PAL.query = query;
    PAL.active = 0;
    PAL.items = paletteItems();
    refine();
    renderPalette();
    dlg.showModal();
    const input = $("palInput");
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
}
function closePalette(restore = true) {
    const dlg = $("palette");
    if (dlg.open)
        dlg.close();
    if (restore && PAL.back && PAL.back.isConnected && PAL.back !== document.body)
        PAL.back.focus?.();
    PAL.items = [];
    PAL.results = [];
}
$("palette").addEventListener("cancel", e => { e.preventDefault(); closePalette(true); });
$("palette").addEventListener("click", e => { if (e.target === $("palette"))
    closePalette(true); }); // the backdrop
// ---- dialogs/shortcuts.tsx
// The shortcut sheet (c0300, design decision 2): `?` prints every command of the registry that has a shortcut,
// by group, with whether it applies to what is shown, and the pointer gestures of the drawing.
const GESTURES = [["Wheel", "Zoom at the pointer"], ["Drag", "Pan (2D) · orbit (3D)"], ["Shift drag", "Pan (3D)"], ["Click", "Select a part, a pad or a net"],
    ["Double-click", "Open a sheet symbol · show the part on the other document"], ["Alt while measuring", "No snapping"]];
function ShortcutSheet() {
    const groups = new Map();
    for (const c of COMMANDS) {
        const keys = c.keys.filter(k => k !== "=" && k !== "_");
        if (!keys.length)
            continue;
        if (!groups.has(c.group))
            groups.set(c.group, []);
        groups.get(c.group).push([c, keys]);
    }
    return preact.h(preact.Fragment, null,
        preact.h("header", { class: "dlgHead" },
            preact.h("h2", { id: "keysTitle" },
                preact.h(Icon, { name: "keyboard" }),
                " Keyboard shortcuts"),
            preact.h("button", { type: "button", class: "tb icon ghost", "aria-label": "Close", "data-tip": "Close", onClick: () => $("shortcuts").close() },
                preact.h(Icon, { name: "x" }))),
        preact.h("div", { class: "keysGrid" },
            [...groups].map(([g, list]) => preact.h("section", { key: g },
                preact.h("h3", null, g),
                preact.h("dl", null, list.map(([c, keys]) => preact.h("div", { class: available(c) ? "" : "na", title: available(c) ? "" : "Not available in this view" },
                    preact.h("dt", null, c.title),
                    preact.h("dd", null, keys.map((k, i) => preact.h(preact.Fragment, null,
                        i ? preact.h("span", { class: "or" }, "or") : null,
                        preact.h("kbd", null, keyLabel(k)))))))))),
            preact.h("section", null,
                preact.h("h3", null, "Pointer"),
                preact.h("dl", null, GESTURES.map(([k, v]) => preact.h("div", null,
                    preact.h("dt", null, v),
                    preact.h("dd", null,
                        preact.h("kbd", null, k))))))),
        preact.h("p", { class: "dlgFoot" },
            "Shortcuts do not act while a text field has the focus; ",
            keyLabel("Mod+K"),
            " opens the palette from anywhere."));
}
function openShortcuts() {
    const dlg = $("shortcuts");
    preact.render(preact.h(ShortcutSheet, null), dlg);
    if (!dlg.open)
        dlg.showModal();
    dlg.querySelector("button")?.focus();
}
$("shortcuts").addEventListener("click", e => { if (e.target === $("shortcuts"))
    $("shortcuts").close(); });
// ---- dialogs/about.tsx
// "About this document" (c0300, design decision 6): the developer detail the status bar no longer shows, one
// click away under the document title: file name and path, size, the full SHA-256 with a copy control, the
// backend, the evidence level of the read, the scene version of a live page and the counts of the notes. Nothing
// in it is new data; it reads the tree's document and the scene's meta.
function fmtBytes(n) {
    if (n == null)
        return "—";
    const unit = n >= 1048576 ? [1048576, "MB"] : n >= 1024 ? [1024, "kB"] : null;
    return unit ? `${(n / unit[0]).toFixed(1)} ${unit[1]} · ${n.toLocaleString("en")} bytes` : `${n} bytes`;
}
function countsOf(meta) {
    const c = meta?.counts || {}, words = { footprints: "parts", components: "parts", pads: "pads", tracks: "tracks", vias: "vias", zones: "zones", pins: "pins", wires: "wires", nets: "nets", items: "items" };
    return Object.entries(words).filter(([k]) => typeof c[k] === "number").map(([k, w]) => `${c[k]} ${w}`).join(" · ");
}
function About() {
    const d = DOC, meta = S && S.meta ? S.meta : {}, notes = (meta.notes || []).length, counts = countsOf(meta);
    const rows = [["Path", d ? d.path : "—"], ["Kind", d ? d.kind : "—"], ["Size", fmtBytes(d ? d.size : null)]];
    return preact.h(preact.Fragment, null,
        preact.h("header", { class: "aboutHead" },
            preact.h("span", { class: "dot", style: `background:${KIND_COLOR[d?.kind] || KIND_COLOR.other}` }),
            preact.h("div", null,
                preact.h("h2", { id: "aboutTitle" }, d ? d.name : "No document"),
                preact.h("p", null, PROJECT ? `${PROJECT.project_file || PROJECT.name} · ${PROJECT.source} project` : "")),
            preact.h("button", { type: "button", class: "tb icon ghost", "aria-label": "Close", "data-tip": "Close", onClick: closeAbout },
                preact.h(Icon, { name: "x" }))),
        preact.h("dl", { class: "aboutRows" },
            rows.map(([k, v]) => preact.h("div", null,
                preact.h("dt", null, k),
                preact.h("dd", null, v))),
            preact.h("div", { class: "hash" },
                preact.h("dt", null, "SHA-256"),
                preact.h("dd", null, meta.sha256 ? preact.h(preact.Fragment, null,
                    preact.h("code", { id: "aboutHash" }, meta.sha256),
                    preact.h("button", { id: "aboutCopy", type: "button", class: "tb small", onClick: () => copyAndSay(meta.sha256, "SHA-256 copied") },
                        preact.h(Icon, { name: "copy" }),
                        preact.h("span", { class: "lbl" }, "Copy"))) : "not read")),
            preact.h("div", null,
                preact.h("dt", null, "Backend"),
                preact.h("dd", null, meta.backend || "—")),
            preact.h("div", null,
                preact.h("dt", null, "Evidence"),
                preact.h("dd", null,
                    preact.h("span", { id: "aboutEvidence", class: "badge" }, meta.evidence || "UNKNOWN"))),
            LIVE ? preact.h("div", null,
                preact.h("dt", null, "Scene version"),
                preact.h("dd", null,
                    preact.h("code", null, st.version || "—"))) : null,
            counts ? preact.h("div", null,
                preact.h("dt", null, "Contents"),
                preact.h("dd", null, counts)) : null,
            preact.h("div", null,
                preact.h("dt", null, "Notes"),
                preact.h("dd", null, notes ? `${notes} note${notes === 1 ? "" : "s"} of the read, listed in the side bar` : "None"))));
}
function aboutOutside(e) { const t = e.target; if (!$("about").contains(t) && !t.closest?.("#bAbout"))
    closeAbout(); }
function aboutKey(e) { if (e.key === "Escape") {
    e.preventDefault();
    e.stopPropagation();
    closeAbout();
    $("bAbout")?.focus();
} }
function openAbout() {
    const dlg = $("about");
    if (dlg.open) {
        closeAbout();
        return;
    }
    preact.render(preact.h(About, null), dlg);
    const b = $("bAbout"), r = b ? b.getBoundingClientRect() : { left: 12, bottom: 44 };
    dlg.style.left = `${Math.max(8, Math.min(r.left - 12, innerWidth - 440))}px`;
    dlg.style.top = `${r.bottom + 8}px`;
    dlg.show();
    dlg.focus();
    document.addEventListener("pointerdown", aboutOutside, true);
    document.addEventListener("keydown", aboutKey, true);
}
function closeAbout() {
    const dlg = $("about");
    if (dlg.open)
        dlg.close();
    document.removeEventListener("pointerdown", aboutOutside, true);
    document.removeEventListener("keydown", aboutKey, true);
}
// ---- panels/toolbar.tsx
// ================================================================== the toolbar (c0300, design decision 3)
// Built from the command registry: the document title with "About this document", then three groups, View
// (2D/3D, Fit, Top/Bottom with the far side's opacity), Tools (Measure with its Point and Edge gap modes, Mark,
// units) and Share (Copy link, Export: SVG and Print at a scale). At the right: Run checks when the server runs
// them, the variant selector, the search field that opens the palette, the theme and the shortcut sheet. A
// control that does not apply to what is shown is not rendered. At 760 px and below the groups show icons only
// and Share moves into the overflow menu.
let DOC_TITLE = "Fenolite viewer";
function setDocTitle(name, base) { DOC_TITLE = name; document.title = (base || name) + " · Fenolite viewer"; refreshToolbar(); }
const keysOf = id => (commandById(id)?.keys || []).filter(k => k !== "=" && k !== "_").map(keyLabel).join(",");
const can = id => { const c = commandById(id); return !!c && available(c); };
const tipOf = id => commandById(id)?.title || id;
function Btn({ id, cmd, icon, text, tip, keys, pressed, onClick, disabled, cls }) {
    const label = tip || (cmd ? tipOf(cmd) : text);
    return preact.h("button", { id: id, type: "button", class: "tb" + (text ? "" : " icon") + (cls ? " " + cls : ""), "aria-label": label, "aria-keyshortcuts": (keys ?? (cmd ? keysOf(cmd) : "")).split(",").filter(Boolean).map(k => k.replace(/ /g, "+")).join(" ") || undefined, "aria-pressed": pressed, "data-tip": label, "data-keys": keys ?? (cmd ? keysOf(cmd) : undefined), disabled: disabled, onClick: onClick || (() => runCommand(cmd)) },
        preact.h(Icon, { name: icon }),
        text ? preact.h("span", { class: "lbl" }, text) : null);
}
function printItems() {
    return COMMANDS.filter(c => c.id.startsWith("share.print.")).map(c => ({ id: "bPrint" + c.id.slice(12).replace("fit", "Fit"), title: c.title.replace("Print · ", ""), icon: "printer", run: () => runCommand(c.id), disabled: !available(c) }));
}
function exportItems() {
    return [{ id: "bSvg", title: "Save as SVG", icon: "image", run: () => runCommand("share.svg"), disabled: !can("share.svg") }, { sep: true }, { heading: "Print, or save as PDF" }, ...printItems()];
}
function OpacityPanel() {
    return preact.h("div", { class: "menuForm" },
        preact.h("label", { for: "opac" },
            "Other side opacity ",
            preact.h("output", null,
                Math.round(st.opac * 100),
                " %")),
        preact.h("input", { id: "opac", type: "range", min: "0", max: "100", value: Math.round(st.opac * 100), onInput: e => { st.opac = +e.target.value / 100; draw(); refreshToolbar(); } }),
        preact.h("p", null, "The layers of the side you look away from, drawn under the near side."));
}
function Toolbar() {
    const boardKind = can("view.3d"), flat = can("tools.measure"), runs = can("app.run");
    const measuring = st.measure || st.edge, variants = variantNames();
    const themeIcon = THEME === "light" ? "sun" : THEME === "dark" ? "moon" : "monitor";
    const shareMenu = [{ id: "bLinkMenu", title: "Copy link", icon: "link", run: () => runCommand("share.link"), disabled: !can("share.link") }, ...exportItems()];
    return preact.h(preact.Fragment, null,
        preact.h("button", { id: "bSidebar", type: "button", class: "tb icon", "aria-controls": "side", "aria-expanded": Boolean($("app").classList.contains("sidebar-open")), "aria-label": "Show or hide the project panels", "data-tip": "Projects and panels", onClick: () => runCommand("app.sidebar") },
            preact.h(Icon, { name: "sidebar" })),
        preact.h("div", { class: "docTitle" },
            preact.h("svg", { class: "mark", width: "20", height: "20", viewBox: "0 0 20 20", "aria-hidden": "true" },
                preact.h("rect", { x: "1", y: "1", width: "18", height: "18", rx: "5", fill: "var(--accent-bg)" }),
                preact.h("path", { d: "M6 14.5V5.5h7M6 10h5", stroke: "var(--accent-text)", "stroke-width": "2", fill: "none", "stroke-linecap": "round", "stroke-linejoin": "round" }),
                preact.h("circle", { cx: "14", cy: "14", r: "1.6", fill: "var(--accent-text)" })),
            preact.h("span", { class: "title", id: "fname", title: DOC_TITLE }, DOC_TITLE),
            DOC ? preact.h(Btn, { id: "bAbout", cmd: "app.about", icon: "info", cls: "ghost" }) : null),
        S ? preact.h("div", { class: "tgroup", role: "group", "aria-label": "View" },
            boardKind ? preact.h("div", { class: "seg", role: "group", "aria-label": "2D or 3D" },
                preact.h(Btn, { id: "b2d", icon: "plane", text: "2D", tip: "2D view", keys: keysOf("view.3d"), pressed: !st.mode3d, onClick: () => { if (st.mode3d)
                        runCommand("view.3d"); } }),
                preact.h(Btn, { id: "b3d", icon: "cube", text: "3D", tip: "3D view", keys: keysOf("view.3d"), pressed: st.mode3d, onClick: () => { if (!st.mode3d)
                        runCommand("view.3d"); } })) : null,
            can("view.fit") ? preact.h(Btn, { id: "bFit", cmd: "view.fit", icon: "fit", text: "Fit" }) : null,
            can("view.flip") ? preact.h("span", { class: "split" },
                preact.h(Btn, { id: "bFlip", cmd: "view.flip", icon: "flip", text: view.mirror ? "Bottom" : "Top", tip: view.mirror ? "Viewed from below: view from above" : "Viewed from above: view from below", pressed: view.mirror }),
                preact.h(Menu, { id: "bFlipMenu", label: "Other side opacity", icon: "chevDown", cls: "caretOnly", panel: OpacityPanel })) : null) : null,
        flat ? preact.h("div", { class: "tgroup", role: "group", "aria-label": "Tools" },
            preact.h("span", { class: "split" },
                preact.h(Btn, { id: "bMeasure", icon: st.edge ? "gap" : "ruler", text: st.edge ? "Edge gap" : "Measure", pressed: measuring, tip: st.edge ? "Edge gap: the gap between the edges of two objects" : "Measure a distance; snaps to pad centres, vertices, then edges (hold Alt: no snap)", keys: st.edge ? keysOf("tools.edge") : keysOf("tools.measure"), onClick: () => runCommand(st.edge ? "tools.edge" : "tools.measure") }),
                can("tools.edge") ? preact.h(Menu, { id: "bMeasureMenu", label: "Measure mode", icon: "chevDown", cls: "caretOnly", items: [
                        { id: "bPoint", title: "Point to point", icon: "ruler", keys: keyLabel("M"), checked: st.measure, run: () => { if (!st.measure)
                                runCommand("tools.measure"); } },
                        { id: "bEdge", title: "Edge gap", icon: "gap", keys: keyLabel("Shift+M"), checked: st.edge, run: () => { if (!st.edge)
                                runCommand("tools.edge"); } },
                    ] }) : null),
            preact.h(Btn, { id: "bMark", cmd: "tools.mark", icon: "pin", text: "Mark", tip: "Drop a review mark with a note", pressed: !!st.marking }),
            preact.h("button", { id: "bUnit", type: "button", class: "tb unit", "aria-label": `Units: ${UNIT === "mm" ? "millimetres" : "mil"}; switch`, "data-tip": "Units: millimetres or mil", "data-keys": keysOf("tools.units"), "aria-keyshortcuts": "Q", onClick: () => runCommand("tools.units") },
                preact.h(Icon, { name: "units" }),
                preact.h("span", { class: "lbl unitv" }, UNIT))) : null,
        DOC ? preact.h("div", { class: "tgroup share", role: "group", "aria-label": "Share" },
            preact.h(Btn, { id: "bLink", cmd: "share.link", icon: "link", text: "Copy link", tip: "Copy a link to this view: document, selection, zoom and unit" }),
            flat ? preact.h(Menu, { id: "bExport", label: "Export", icon: "download", text: "Export", caret: true, items: exportItems(), tip: "Export: save as SVG or print" }) : null) : null,
        preact.h("div", { class: "tspacer" }),
        runs ? preact.h(Btn, { id: "bRun", cmd: "app.run", icon: "play", text: "Run checks", cls: "runBtn", disabled: !!RUNS.job, tip: RUNS.job ? "A run is in progress" : "Run checks on this server (read-only; nothing is written)" }) : null,
        variants.length ? preact.h("select", { id: "variantSel", class: "tbSelect", "aria-label": "Assembly variant", "data-tip": "The project's assembly variant", onChange: e => setVariant(e.target.value) },
            preact.h("option", { value: "", selected: !VARIANT }, "[No Variations]"),
            variants.map(n => preact.h("option", { selected: n === VARIANT }, n))) : null,
        preact.h("div", { class: "searchBox", role: "search" },
            preact.h(Icon, { name: "search" }),
            preact.h("input", { id: "search", placeholder: "Search or run\u2026", "aria-label": "Search parts, nets, documents and commands", autocomplete: "off", spellcheck: false, onKeyDown: e => { const t = e.target; if (e.key === "Enter") {
                    const q = t.value;
                    t.value = "";
                    if (q.trim())
                        openPalette(q);
                    else
                        find(q);
                    t.blur();
                }
                else if (e.key === "Escape")
                    t.blur();
                else if (e.key === "ArrowDown") {
                    e.preventDefault();
                    openPalette(t.value);
                    t.value = "";
                } }, onInput: e => { const t = e.target; const q = t.value; t.value = ""; openPalette(q); } }),
            preact.h("kbd", { class: "searchKey", onClick: () => openPalette() }, keyLabel("Mod+K"))),
        preact.h("span", { class: "tgroup end" },
            preact.h(Menu, { id: "bMore", label: "More", icon: "more", cls: "onlyNarrow", align: "right", items: shareMenu, tip: "Share and export" }),
            preact.h(Menu, { id: "bTheme", label: "Interface theme", icon: themeIcon, align: "right", tip: "Interface theme", items: [
                    { heading: "Interface theme" },
                    { id: "themeSystem", title: "Follow the system", icon: "monitor", radio: true, checked: THEME === "system", run: () => runCommand("app.theme.system") },
                    { id: "themeLight", title: "Light", icon: "sun", radio: true, checked: THEME === "light", run: () => runCommand("app.theme.light") },
                    { id: "themeDark", title: "Dark", icon: "moon", radio: true, checked: THEME === "dark", run: () => runCommand("app.theme.dark") },
                ] }),
            preact.h(Btn, { id: "bKeys", cmd: "app.shortcuts", icon: "keyboard", cls: "hideNarrow" }),
            S ? preact.h(Btn, { id: "bDock", cmd: "view.dock", icon: "dock", tip: dockNarrow() ? "Properties" : "Show or hide the inspector", pressed: dockNarrow() ? DOCK.sheet : DOCK.open }) : null));
}
var TOOLBAR_READY = false; // var: read before this module runs by the modules that come first
function toolbarReady() { TOOLBAR_READY = true; refreshToolbar(); }
function refreshToolbar() { if (TOOLBAR_READY)
    preact.render(preact.h(Toolbar, null), $("top")); }
// ---- core/start.ts
// ================================================================== start: embedded data or the live server
async function start() {
    if (EMBED) {
        setProject(EMBED.project);
        for (const [id, sc] of Object.entries(EMBED.scenes))
            RAW.set(id, sc);
    } // decoded when opened
    else if (LIVE) {
        setProject(await (await fetch("project.json", { cache: "no-store" })).json());
    }
    document.body.classList.toggle("catalog", PROJECT?.source === "catalog");
    toolbarReady();
    refreshStatus();
    reviewEntry();
    refreshDock();
    refreshSummary();
    buildTree();
    loadMarks((EMBED && EMBED.marks) || (PROJECT && PROJECT.marks));
    buildMarks();
    const docs = PROJECT ? PROJECT.groups.flatMap(g => g.documents) : [];
    const link = new URLSearchParams(location.hash.slice(1)); // c0189: a link opens where it was made
    const want = link.get("doc") || (EMBED && EMBED.open) || (PROJECT && PROJECT.open);
    const d = docs.find(x => x.id === want) || docs.find(x => x.viewable && x.present) || docs[0];
    const shown = d ? await openDoc(d) : 0;
    if (shown && shown === navigation) {
        if (link.get("doc") && DOC && DOC.id === link.get("doc"))
            applyLink(link);
        else
            applySelect((EMBED && EMBED.select) || (PROJECT && PROJECT.select));
        if (link.get("item") && LIB) {
            const i = LIB.items.findIndex(item => item.name === link.get("item"));
            if (i >= 0)
                openItem(i);
        }
    }
    setLinkReady(true);
    if (LIVE)
        setInterval(poll, 2000);
    runsInit(); // c0302: asks a live server whether it runs checks
}
async function poll() {
    if (!DOC || !DOC.viewable || loadingNavigation === navigation)
        return;
    const doc = DOC, request = (POLLS.get(doc.id) || 0) + 1;
    let generation = navigation;
    POLLS.set(doc.id, request);
    const current = () => generation === navigation && DOC.id === doc.id && POLLS.get(doc.id) === request;
    try {
        const v = await (await fetch(`version/${encodeURIComponent(doc.id)}`, { cache: "no-store" })).json();
        if (!current())
            return;
        liveState(v.error ? "err" : v.building ? "busy" : "ok", v.error ? `Read error: ${v.error}` : v.building ? "Building…" : v.updated ? `Live · updated ${v.updated}` : "Live");
        if (v.building)
            return;
        if (v.version && v.version !== st.version) {
            invalidateScene(doc.id);
            const opening = openDoc(doc, true);
            generation = navigation;
            const shown = await opening;
            if (!shown || shown !== generation || !current())
                return;
        }
        st.version = v.version || st.version;
    }
    catch (e) {
        if (current())
            liveState("err", "Server not reachable");
    }
}
function liveState(kind, text) { const el = $("live"); el.textContent = text; el.dataset.state = kind; el.hidden = !text; }
// ---- main.ts
// The page's entry (change c0304): every module, imported for its effect in link order, then start().
start();

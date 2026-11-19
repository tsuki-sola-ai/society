// 閲覧数の表示。GoatCounterが応答しないときや、まだ0回のときは何も出さない。
const GOATCOUNTER = 'https://tsuki-sola.goatcounter.com';

window.viewCount = (path) => fetch(GOATCOUNTER + '/counter/' + encodeURIComponent(path) + '.json')
  .then((r) => (r.ok ? r.json() : null))
  .then((d) => (d && d.count != null && /[1-9]/.test(String(d.count)) ? String(d.count) : null))
  .catch(() => null);

// data-views="page" はこのページ、data-views="TOTAL" はサイト全体の回数を入れる
document.querySelectorAll('[data-views]').forEach((el) => {
  const path = el.dataset.views === 'TOTAL' ? 'TOTAL' : location.pathname;
  window.viewCount(path).then((n) => {
    if (!n) return;
    el.querySelector('[data-views-n]').textContent = n;
    el.hidden = false;
  });
});

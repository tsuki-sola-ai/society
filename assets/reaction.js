// 反応ボタン。ページの下に「役に立った」「分かりにくい」の2択を置き、押された回数を GoatCounter のイベントとして数える。
// 件数は公開ページには出さない(管理ページで見る)。置き方: <section data-reaction hidden></section> と、このファイルの読み込み。
(() => {
  const CHOICES = [['useful', '役に立った'], ['unclear', '分かりにくい']];
  const ISSUES = 'https://github.com/tsuki-sola-ai/society/issues/new';
  const normalize = (path) => (path.length > 1 ? path.replace(/\/+$/, '') : path);

  // イベント名は「reaction-種類 + ページのパス」(例: reaction-useful/society/nenkin)。管理ページも同じ名前で件数を引く
  window.reactionEvent = (kind, path) => 'reaction-' + kind + normalize(path);
  window.reactionChoices = CHOICES;

  const box = document.querySelector('[data-reaction]');
  if (!box) return;

  const key = 'reaction:' + normalize(location.pathname);
  // 押したことの記憶は、その人のブラウザの中だけ。使えない環境でも動くようにしておく
  const recall = () => { try { return localStorage.getItem(key); } catch (e) { return null; } };
  const remember = (kind) => { try { localStorage.setItem(key, kind); } catch (e) { /* 覚えられなくても支障はない */ } };
  const mk = (tag, text, cls) => { const e = document.createElement(tag); if (text != null) e.textContent = text; if (cls) e.className = cls; return e; };

  const thanks = (kind) => {
    const p = mk('p', 'ありがとうございます。', 'muted');
    if (kind === 'unclear') {
      const a = mk('a', 'GitHubのIssue'); a.href = ISSUES;
      p.append('どこが分かりにくかったか、よければ', a, 'で教えてください。');
    }
    return p;
  };

  // 広告ブロックなどで集計の部品が読み込まれていないとき、数えない設定(自分の閲覧の除外など)のときは false
  const send = (kind) => {
    const gc = window.goatcounter;
    if (!gc || typeof gc.count !== 'function') return false;
    if (typeof gc.filter === 'function' && gc.filter()) return false;
    const label = CHOICES.find(([k]) => k === kind)[1];
    gc.count({path: window.reactionEvent(kind, location.pathname), title: label + ': ' + document.title, event: true});
    return true;
  };

  box.className = 'reaction';
  box.setAttribute('aria-live', 'polite');
  const done = recall();
  if (done) {
    box.replaceChildren(thanks(done));
  } else {
    const row = mk('div', null, 'reaction-row');
    row.append(...CHOICES.map(([kind, label]) => {
      const b = mk('button', label); b.type = 'button';
      b.addEventListener('click', () => {
        if (send(kind)) { remember(kind); box.replaceChildren(thanks(kind)); }
        else box.replaceChildren(mk('p', '記録できませんでした。広告ブロックなどを使っていると、数えられないことがあります。', 'muted'));
      });
      return b;
    }));
    box.replaceChildren(mk('p', 'このページは役に立ちましたか。', 'muted'), row);
  }
  box.hidden = false;
})();

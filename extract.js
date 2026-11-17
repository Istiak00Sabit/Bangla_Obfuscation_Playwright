/* Read rendered nodes only. No page script, network API or hidden response parsing.
 * Message-node textContent is retained unnormalized, with innerText alongside it.
 * Generic article fallback is explicitly marked because it can contain UI labels.
 */
() => {
  window.__obfuscationCollector ??= {nodes: new WeakMap(), serial: 0};
  const state = window.__obfuscationCollector;
  const key = node => {
    if (!state.nodes.has(node)) state.nodes.set(node, String(++state.serial));
    return state.nodes.get(node);
  };
  const visible = node => {
    const s = getComputedStyle(node);
    return s.display !== 'none' && s.visibility !== 'hidden' &&
      node.getClientRects().length > 0 && !node.closest('[aria-hidden="true"]');
  };
  const selector = '[data-ad-preview="message"], [data-ad-comet-preview="message"], ' +
    '[data-ad-rendering-role="story_message"], [data-ad-comet-preview="comment"], ' +
    '[data-obfuscation-message]';
  const articles = [...document.querySelectorAll('[role="article"], article')].filter(visible);
  const messages = [...document.querySelectorAll(selector)].filter(visible);
  const rows = [], used = new Set();

  function nearestArticle(node) { return node.closest('[role="article"], article'); }
  function ownedMessages(article) {
    return messages.filter(m => nearestArticle(m) === article);
  }
  function linkFor(article, kind) {
    if (!article) return '';
    const links = [...article.querySelectorAll('a[href]')]
      .filter(a => visible(a) && nearestArticle(a) === article);
    const comment = links.find(a => /[?&](comment_id|reply_comment_id)=/.test(a.href));
    if (kind === 'comment' && comment) return comment.href;
    const post = links.find(a => /\/posts\/|\/permalink\/|story_fbid=|\/videos\//.test(a.href));
    return kind === 'comment' ? '' : (post?.href || '');
  }
  function inferKind(node, article) {
    if (node.matches('[data-ad-comet-preview="comment"]') ||
        node.closest('[data-obfuscation-kind="comment"]')) return 'comment';
    if (article?.parentElement?.closest('[role="article"], article')) return 'comment';
    if (node.matches('[data-ad-preview="message"], [data-ad-comet-preview="message"], ' +
        '[data-ad-rendering-role="story_message"]')) return 'post';
    return 'unknown';
  }
  function push(node, article, method, explicitKind) {
    if (used.has(node)) return;
    const raw = node.textContent || '';
    if (!raw.trim()) return;
    used.add(node);
    const kind = explicitKind || inferKind(node, article);
    rows.push({
      dom_node_key: key(node), kind,
      raw_text: raw,
      visible_text: node.innerText || raw,
      extraction_method: method,
      item_url: linkFor(article, kind),
      context_text: (article?.innerText || node.innerText || raw),
      parent_dom_key: article?.parentElement?.closest('[role="article"], article')
        ? key(article.parentElement.closest('[role="article"], article')) : '',
      article_dom_key: article ? key(article) : '',
      message_slot: article ? ownedMessages(article).filter(n => !n.querySelector(selector)).indexOf(node) : 0,
      has_see_more_control: [...(article || node).querySelectorAll('button, [role="button"]')]
        .some(n => /^(see more|আরও দেখুন)$/i.test(n.innerText.trim())),
    });
  }

  // Avoid duplicate wrapper/message nodes covering the same content.
  for (const node of messages) {
    if (node.querySelector(selector)) continue;
    push(node, nearestArticle(node), 'message_node_text_content');
  }
  for (const article of articles) {
    if (ownedMessages(article).length) continue;
    if (article.querySelector('[role="article"], article')) {
      // Last-resort top-level text without child comments, so comments are not
      // silently merged into the post. This record may still contain UI text.
      const clone = article.cloneNode(true);
      clone.querySelectorAll('[role="article"], article, button, [role="button"], script, style')
        .forEach(n => n.remove());
      if (clone.textContent.trim()) {
        push(article, article, 'article_fallback_with_ui');
        rows.at(-1).raw_text = clone.textContent;
      }
      continue;
    }
    push(article, article, 'article_fallback_with_ui');
  }

  // This manifest does not download images or claim to transcribe image text.
  const images = [...document.querySelectorAll('img[src]')].filter(img => {
    const box = img.getBoundingClientRect();
    return visible(img) && box.width >= 120 && box.height >= 80 &&
      !!img.closest('[role="article"], article');
  }).map(img => ({
    dom_node_key: key(img), image_url: img.currentSrc || img.src,
    alt_text: img.alt || '', width: img.naturalWidth, height: img.naturalHeight,
    article_dom_key: key(nearestArticle(img)), requires_visual_review: true,
    ocr_status: 'not_transcribed',
  }));
  return {records: rows, images, article_count: articles.length, message_count: messages.length};
}

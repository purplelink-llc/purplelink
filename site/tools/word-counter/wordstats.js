// Document Insights — pure client-side statistics engine.
//
// No network calls. Every function operates on a plain-text string and
// returns plain data. Both the paste path and the upload path (after the
// backend extracts text) call analyze() here, so the math is identical and
// runs entirely in the user's browser.
//
// Exposed on window.WordStats. Loaded as an external script (CSP: no inline).
(function () {
  "use strict";

  // ---------------------------------------------------------------------
  // Tokenisation primitives
  // ---------------------------------------------------------------------

  function words(text) {
    var t = (text || "").trim();
    if (!t) return [];
    return t.split(/\s+/).filter(function (w) { return w.length > 0; });
  }

  // "Real" word tokens for linguistic stats — letters/digits only, lowercased.
  function lexicalWords(text) {
    var m = (text || "").toLowerCase().match(/[a-z0-9']+/g);
    return m || [];
  }

  function sentences(text) {
    var m = (text || "").match(/[^.!?]+[.!?]+(?=\s|$)/g);
    if (m && m.length) return m.map(function (s) { return s.trim(); });
    return (text || "").trim() ? [text.trim()] : [];
  }

  function paragraphs(text) {
    if (!(text || "").trim()) return [];
    return text.split(/\n\s*\n+/).map(function (p) { return p.trim(); })
      .filter(function (p) { return p.length > 0; });
  }

  // ---------------------------------------------------------------------
  // Syllable estimation (heuristic — good enough for grade-level metrics)
  // ---------------------------------------------------------------------

  function syllableCount(word) {
    word = word.toLowerCase().replace(/[^a-z]/g, "");
    if (!word) return 0;
    if (word.length <= 3) return 1;
    word = word.replace(/(?:[^laeiouy]es|ed|[^laeiouy]e)$/, "");
    word = word.replace(/^y/, "");
    var groups = word.match(/[aeiouy]{1,2}/g);
    return groups ? groups.length : 1;
  }

  function totalSyllables(wordList) {
    var n = 0;
    for (var i = 0; i < wordList.length; i++) n += syllableCount(wordList[i]);
    return n;
  }

  function countComplexWords(wordList) {
    // Gunning Fog "complex" = 3+ syllables (excluding common suffix inflations)
    var n = 0;
    for (var i = 0; i < wordList.length; i++) {
      if (syllableCount(wordList[i]) >= 3) n++;
    }
    return n;
  }

  // ---------------------------------------------------------------------
  // Basic counts
  // ---------------------------------------------------------------------

  function basicCounts(text) {
    var w = words(text);
    var s = sentences(text);
    var p = paragraphs(text);
    var chars = (text || "").length;
    var charsNoSpace = (text || "").replace(/\s/g, "").length;
    return {
      words: w.length,
      characters: chars,
      charactersNoSpaces: charsNoSpace,
      sentences: s.length,
      paragraphs: p.length,
      readingMinutes: Math.max(0, Math.ceil(w.length / 200)),
      speakingMinutes: Math.max(0, Math.ceil(w.length / 130)),
      // ~500 words per double-spaced manuscript page is a common convention
      pageEquivalents: w.length ? Math.max(1, Math.round(w.length / 500)) : 0,
    };
  }

  // ---------------------------------------------------------------------
  // Readability
  // ---------------------------------------------------------------------

  function readability(text) {
    var lw = lexicalWords(text);
    var sents = sentences(text);
    var nWords = lw.length;
    var nSents = Math.max(1, sents.length);
    var nSyll = totalSyllables(lw);
    var nChars = lw.join("").length;
    var nComplex = countComplexWords(lw);

    if (nWords === 0) {
      return null;
    }

    var wordsPerSentence = nWords / nSents;
    var syllPerWord = nSyll / nWords;

    var flesch = 206.835 - 1.015 * wordsPerSentence - 84.6 * syllPerWord;
    var fkGrade = 0.39 * wordsPerSentence + 11.8 * syllPerWord - 15.59;
    var fog = 0.4 * (wordsPerSentence + 100 * (nComplex / nWords));
    // SMOG needs >=30 sentences for accuracy; we still report with a note.
    var smog = 1.0430 * Math.sqrt(nComplex * (30 / nSents)) + 3.1291;
    var lettersPer100 = (nChars / nWords) * 100;
    var sentsPer100 = (nSents / nWords) * 100;
    var coleman = 0.0588 * lettersPer100 - 0.296 * sentsPer100 - 15.8;
    var ari = 4.71 * (nChars / nWords) + 0.5 * wordsPerSentence - 21.43;

    function r1(x) { return Math.round(x * 10) / 10; }

    return {
      fleschReadingEase: r1(Math.max(0, Math.min(100, flesch))),
      fleschKincaidGrade: r1(Math.max(0, fkGrade)),
      gunningFog: r1(Math.max(0, fog)),
      smog: r1(Math.max(0, smog)),
      colemanLiau: r1(Math.max(0, coleman)),
      automatedReadabilityIndex: r1(Math.max(0, ari)),
      avgWordsPerSentence: r1(wordsPerSentence),
      avgSyllablesPerWord: r1(syllPerWord),
      smogReliable: nSents >= 30,
      interpretation: fleschInterpretation(flesch),
    };
  }

  function fleschInterpretation(score) {
    if (score >= 90) return "Very easy (5th grade)";
    if (score >= 80) return "Easy (6th grade)";
    if (score >= 70) return "Fairly easy (7th grade)";
    if (score >= 60) return "Standard (8th-9th grade)";
    if (score >= 50) return "Fairly difficult (10th-12th grade)";
    if (score >= 30) return "Difficult (college)";
    return "Very difficult (graduate / academic)";
  }

  // ---------------------------------------------------------------------
  // Vocabulary
  // ---------------------------------------------------------------------

  var STOPWORDS = {};
  ("the of and a to in is was he for it with as his on be at by i this had not are but from or " +
   "have an they which one you were her all she there would their we him been has when who will " +
   "more no if out so said what up its about into than them can only other new some could time " +
   "these two may then do first any my now such like our over man me even most made after also " +
   "did many before must through back years where much your way well down should because each just " +
   "those people mr how too little state good very make world still own see men work long get here " +
   "between both life being under never day same another know while last might us great old year off " +
   "come since against go came right used take three states himself few house use during without again " +
   "place american around however home small found mrs thought went say part once general high upon " +
   "school every don does got united left number course war until always away something fact though " +
   "water less public put thing almost hand enough far took head yet government system set told nothing " +
   "end why called didn eyes find going look asked later knew").split(" ").forEach(function (w) {
    STOPWORDS[w] = true;
  });

  function vocabulary(text) {
    var lw = lexicalWords(text);
    if (lw.length === 0) return null;
    var freq = {};
    var bigramFreq = {};
    var prev = null;
    for (var i = 0; i < lw.length; i++) {
      var w = lw[i];
      freq[w] = (freq[w] || 0) + 1;
      if (prev && !STOPWORDS[prev] && !STOPWORDS[w]) {
        var bg = prev + " " + w;
        bigramFreq[bg] = (bigramFreq[bg] || 0) + 1;
      }
      prev = w;
    }
    var unique = Object.keys(freq);
    var hapax = unique.filter(function (w) { return freq[w] === 1; });

    function topN(obj, n, filterStop) {
      return Object.keys(obj)
        .filter(function (k) { return !filterStop || !STOPWORDS[k]; })
        .map(function (k) { return { term: k, count: obj[k] }; })
        .sort(function (a, b) { return b.count - a.count || a.term.localeCompare(b.term); })
        .slice(0, n);
    }

    return {
      totalTokens: lw.length,
      uniqueWords: unique.length,
      typeTokenRatio: Math.round((unique.length / lw.length) * 1000) / 1000,
      hapaxCount: hapax.length,
      hapaxRatio: Math.round((hapax.length / lw.length) * 1000) / 1000,
      topWords: topN(freq, 15, true),
      topBigrams: topN(bigramFreq, 10, false),
    };
  }

  // ---------------------------------------------------------------------
  // Sentence-length stats
  // ---------------------------------------------------------------------

  function sentenceStats(text) {
    var sents = sentences(text);
    if (sents.length === 0) return null;
    var lengths = sents.map(function (s) { return words(s).length; })
      .filter(function (n) { return n > 0; });
    if (lengths.length === 0) return null;
    var sorted = lengths.slice().sort(function (a, b) { return a - b; });
    var sum = sorted.reduce(function (a, b) { return a + b; }, 0);
    function pct(p) {
      var idx = Math.min(sorted.length - 1, Math.floor(p * sorted.length));
      return sorted[idx];
    }
    var longestIdx = lengths.indexOf(Math.max.apply(null, lengths));
    // Histogram buckets
    var buckets = [
      { label: "1-10", min: 1, max: 10, n: 0 },
      { label: "11-20", min: 11, max: 20, n: 0 },
      { label: "21-30", min: 21, max: 30, n: 0 },
      { label: "31-40", min: 31, max: 40, n: 0 },
      { label: "41+", min: 41, max: Infinity, n: 0 },
    ];
    lengths.forEach(function (l) {
      for (var i = 0; i < buckets.length; i++) {
        if (l >= buckets[i].min && l <= buckets[i].max) { buckets[i].n++; break; }
      }
    });
    return {
      count: lengths.length,
      avg: Math.round((sum / lengths.length) * 10) / 10,
      median: pct(0.5),
      p95: pct(0.95),
      longest: Math.max.apply(null, lengths),
      longestPreview: (sents[longestIdx] || "").slice(0, 220),
      histogram: buckets,
    };
  }

  // ---------------------------------------------------------------------
  // Style flags (each returns {count, density, matches:[...] })
  // ---------------------------------------------------------------------

  function flagPatterns(text, patterns) {
    var matches = [];
    var lower = text || "";
    patterns.forEach(function (re) {
      var m;
      re.lastIndex = 0;
      while ((m = re.exec(lower)) !== null) {
        matches.push({ text: m[0].trim(), index: m.index });
        if (matches.length > 500) break; // safety cap
        if (!re.global) break;
      }
    });
    matches.sort(function (a, b) { return a.index - b.index; });
    return matches;
  }

  function styleFlags(text) {
    var nWords = words(text).length || 1;

    var passiveRe = [/\b(?:is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?\w+(?:ed|en)\b/gi];
    var adverbRe = [/\b\w+ly\b/gi];
    var weaselRe = [/\b(?:very|really|quite|rather|somewhat|fairly|actually|basically|simply|just|literally|truly|extremely)\b/gi];
    var hedgeRe = [/\b(?:might|maybe|perhaps|possibly|seems?|appears?|suggests?|could|relatively|arguably|presumably|likely|tend(?:s|ed)? to)\b/gi];
    var clicheRe = [/\b(?:novel|to the best of our knowledge|it is worth noting|interestingly|notably|importantly|paradigm shift|state-of-the-art|cutting-edge|paves? the way|sheds? light)\b/gi];

    function pack(matches) {
      return {
        count: matches.length,
        densityPer100: Math.round((matches.length / nWords) * 10000) / 100,
        matches: matches.slice(0, 50),
      };
    }

    return {
      passive: pack(flagPatterns(text, passiveRe)),
      adverbs: pack(flagPatterns(text, adverbRe)),
      weasel: pack(flagPatterns(text, weaselRe)),
      hedge: pack(flagPatterns(text, hedgeRe)),
      cliche: pack(flagPatterns(text, clicheRe)),
    };
  }

  // ---------------------------------------------------------------------
  // AI-writing-pattern audit  (NOT an AI detector — see disclaimer in UI)
  // ---------------------------------------------------------------------

  function aiPatternAudit(text) {
    var nWords = words(text).length || 1;
    var phraseRe = [
      /\bdelve(?:s|d)? into\b/gi,
      /\bit'?s worth noting\b/gi,
      /\bit is important to note\b/gi,
      /\bin today'?s (?:fast-paced |digital )?world\b/gi,
      /\ba testament to\b/gi,
      /\btapestry\b/gi,
      /\bnavigat(?:e|ing) the (?:complexities|landscape|world)\b/gi,
      /\bin the realm of\b/gi,
      /\bunlock(?:ing)? the (?:potential|power|secrets)\b/gi,
      /\bplays? a (?:crucial|pivotal|vital|significant) role\b/gi,
      /\bunderscore(?:s|d)? the importance\b/gi,
      /\bfoster(?:s|ing)? (?:a sense of|innovation|collaboration)\b/gi,
      /\bmoreover,\b/gi,
      /\bfurthermore,\b/gi,
      /\bin conclusion,\b/gi,
      /\bnot only\b[^.]*\bbut also\b/gi,
      /\bwhen it comes to\b/gi,
      /\bharness(?:ing)? the\b/gi,
      /\bgame-?changer\b/gi,
      /\bever-(?:evolving|changing|growing)\b/gi,
    ];
    var matches = flagPatterns(text, phraseRe);

    // Em-dash density — LLM prose tends to over-use em dashes.
    var emDashes = (text.match(/—/g) || []).length;
    var emDashPer1k = Math.round((emDashes / nWords) * 10000) / 10;

    return {
      flaggedPhraseCount: matches.length,
      densityPer1000Words: Math.round((matches.length / nWords) * 100000) / 100,
      emDashCount: emDashes,
      emDashPer1000Words: emDashPer1k,
      matches: matches.slice(0, 60),
      // No score, no verdict. The UI shows a strong disclaimer.
    };
  }

  // ---------------------------------------------------------------------
  // Character-set anomalies (reuses the regex set from backend safety.py)
  // ---------------------------------------------------------------------

  function charAnomalies(text) {
    var invisible = (text.match(/[​-‏‪-‮⁠-⁤⁪-⁯﻿­]/g) || []).length;
    var controls = (text.match(/[ ---]/g) || []).length;
    var fullwidth = (text.match(/[！-～]/g) || []).length;
    var smartQuotes = (text.match(/[‘’“”]/g) || []).length;
    var straightQuotes = (text.match(/["']/g) || []).length;
    // Mixed-script: presence of both Latin and Cyrillic/Greek letters
    var hasLatin = /[A-Za-z]/.test(text);
    var hasCyrillic = /[Ѐ-ӿ]/.test(text);
    var hasGreek = /[Ͱ-Ͽ]/.test(text);
    return {
      invisibleChars: invisible,
      controlChars: controls,
      fullwidthChars: fullwidth,
      smartQuotes: smartQuotes,
      straightQuotes: straightQuotes,
      mixedScript: hasLatin && (hasCyrillic || hasGreek),
      anyAnomaly: invisible > 0 || controls > 0 || (hasLatin && (hasCyrillic || hasGreek)),
    };
  }

  // ---------------------------------------------------------------------
  // Citation density
  // ---------------------------------------------------------------------

  function citationStats(text) {
    var nWords = words(text).length || 1;
    var numeric = (text.match(/\[\s*\d+(?:\s*[-,]\s*\d+)*\s*\]/g) || []).length;
    var authorYear = (text.match(/\([A-Z][A-Za-z]+(?:\s+(?:et al\.?|and|&)\s+[A-Z][A-Za-z]+)*,?\s+(?:19|20)\d{2}[a-z]?\)/g) || []).length;
    var total = numeric + authorYear;
    return {
      numericCitations: numeric,
      authorYearCitations: authorYear,
      total: total,
      perThousandWords: Math.round((total / nWords) * 100000) / 100,
    };
  }

  // ---------------------------------------------------------------------
  // Top-level orchestration
  // ---------------------------------------------------------------------

  function analyze(text, sections) {
    text = text || "";
    var out = {
      basic: basicCounts(text),
      readability: readability(text),
      vocabulary: vocabulary(text),
      sentences: sentenceStats(text),
      style: styleFlags(text),
      aiPatterns: aiPatternAudit(text),
      anomalies: charAnomalies(text),
      citations: citationStats(text),
    };
    if (sections && typeof sections === "object") {
      out.sections = sectionBreakdown(sections);
    }
    return out;
  }

  // Per-section word counts + readability, plus building blocks for the
  // "combination" toggles in the UI.
  function sectionBreakdown(sections) {
    var out = {};
    Object.keys(sections).forEach(function (key) {
      var val = sections[key];
      if (Array.isArray(val)) val = val.join("\n\n");
      if (typeof val !== "string" || !val.trim()) return;
      out[key] = {
        words: words(val).length,
        readability: readability(val),
        text: val,
      };
    });
    return out;
  }

  // CSV export of a flat stats object → string
  function toCSV(stats) {
    var rows = [["Metric", "Value"]];
    var b = stats.basic || {};
    rows.push(["Words", b.words]);
    rows.push(["Characters (with spaces)", b.characters]);
    rows.push(["Characters (no spaces)", b.charactersNoSpaces]);
    rows.push(["Sentences", b.sentences]);
    rows.push(["Paragraphs", b.paragraphs]);
    rows.push(["Reading time (min)", b.readingMinutes]);
    rows.push(["Speaking time (min)", b.speakingMinutes]);
    rows.push(["Page-equivalents", b.pageEquivalents]);
    if (stats.readability) {
      var r = stats.readability;
      rows.push(["Flesch Reading Ease", r.fleschReadingEase]);
      rows.push(["Flesch-Kincaid Grade", r.fleschKincaidGrade]);
      rows.push(["Gunning Fog", r.gunningFog]);
      rows.push(["SMOG", r.smog]);
      rows.push(["Coleman-Liau", r.colemanLiau]);
      rows.push(["Automated Readability Index", r.automatedReadabilityIndex]);
      rows.push(["Avg words/sentence", r.avgWordsPerSentence]);
      rows.push(["Avg syllables/word", r.avgSyllablesPerWord]);
    }
    if (stats.vocabulary) {
      var v = stats.vocabulary;
      rows.push(["Unique words", v.uniqueWords]);
      rows.push(["Type-token ratio", v.typeTokenRatio]);
      rows.push(["Hapax legomena", v.hapaxCount]);
    }
    if (stats.sentences) {
      rows.push(["Avg sentence length", stats.sentences.avg]);
      rows.push(["Median sentence length", stats.sentences.median]);
      rows.push(["95th pct sentence length", stats.sentences.p95]);
    }
    if (stats.style) {
      rows.push(["Passive-voice instances", stats.style.passive.count]);
      rows.push(["Adverbs", stats.style.adverbs.count]);
      rows.push(["Weasel words", stats.style.weasel.count]);
      rows.push(["Hedge words", stats.style.hedge.count]);
      rows.push(["Academic clichés", stats.style.cliche.count]);
    }
    if (stats.aiPatterns) {
      rows.push(["AI-pattern phrases flagged", stats.aiPatterns.flaggedPhraseCount]);
      rows.push(["Em-dashes", stats.aiPatterns.emDashCount]);
    }
    if (stats.citations) {
      rows.push(["Citations (total)", stats.citations.total]);
      rows.push(["Citations per 1000 words", stats.citations.perThousandWords]);
    }
    if (stats.sections) {
      Object.keys(stats.sections).forEach(function (k) {
        rows.push(["Section: " + k + " (words)", stats.sections[k].words]);
      });
    }
    return rows.map(function (row) {
      return row.map(function (cell) {
        var s = String(cell == null ? "" : cell);
        return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
      }).join(",");
    }).join("\n");
  }

  window.WordStats = {
    analyze: analyze,
    basicCounts: basicCounts,
    readability: readability,
    vocabulary: vocabulary,
    sentenceStats: sentenceStats,
    styleFlags: styleFlags,
    aiPatternAudit: aiPatternAudit,
    charAnomalies: charAnomalies,
    citationStats: citationStats,
    toCSV: toCSV,
    words: words,
  };
})();

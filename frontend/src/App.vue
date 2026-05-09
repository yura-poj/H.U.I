<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:5001/api").replace(/\/+$/, "");
const RECENT_HISTORY_LIMIT = 5;

const username = ref("");
const password = ref("");
const token = ref(localStorage.getItem("hui_token") || "");
const user = ref(JSON.parse(localStorage.getItem("hui_user") || "null"));
const levels = ref([]);
const game = ref(null);
const insult = ref("");
const mode = ref("login");
const loading = ref(false);
const error = ref("");
const events = ref([]);
const activeView = ref("game");
const history = ref([]);
const leaderboard = ref([]);
const currentUserRank = ref(null);
const leaderboardSection = ref("top");
const leaderboardPage = ref(1);
const panelLoading = ref(false);
const monsterHit = ref(false);
const floatingDamage = ref(null);
const monsterSpeech = ref("");
const monsterTimers = [];

const isAuthed = computed(() => Boolean(token.value && user.value));
const currentLevel = computed(() => {
  if (!game.value) {
    return levels.value.find((level) => level.id === user.value?.current_level_id);
  }

  return levels.value.find((level) => level.id === game.value.level_id);
});
const hpPercent = computed(() => {
  if (!game.value) {
    return 0;
  }

  return Math.max(0, Math.round((game.value.monster.hp / game.value.monster.max_hp) * 100));
});
const requiredWords = computed(() => game.value?.rules.min_words_per_insult || 0);
const insultWordCount = computed(() => countWords(insult.value));
const wordRuleMet = computed(() => {
  if (!requiredWords.value) {
    return false;
  }

  return insultWordCount.value >= requiredWords.value;
});
const totalDamage = computed(() => history.value.reduce((sum, item) => sum + item.damage, 0));
const totalInsults = computed(() => history.value.length);
const recentHistory = computed(() => history.value.slice(0, RECENT_HISTORY_LIMIT));

class ApiError extends Error {
  constructor(status, data) {
    super(data.error || `request_failed_${status}`);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

function rememberSession(nextToken, nextUser) {
  token.value = nextToken;
  user.value = nextUser;
  localStorage.setItem("hui_token", nextToken);
  localStorage.setItem("hui_user", JSON.stringify(nextUser));
}

function clearSession() {
  resetMonsterEffects();
  token.value = "";
  user.value = null;
  game.value = null;
  events.value = [];
  history.value = [];
  leaderboard.value = [];
  currentUserRank.value = null;
  activeView.value = "game";
  localStorage.removeItem("hui_token");
  localStorage.removeItem("hui_user");
}

function logout() {
  error.value = "";
  clearSession();
}

function pushEvent(entry) {
  events.value = [{ id: `${Date.now()}-${events.value.length}`, ...entry }, ...events.value].slice(0, 8);
}

async function request(path, options = {}) {
  const headers = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(token.value ? { Authorization: `Bearer ${token.value}` } : {}),
    ...options.headers,
  };

  const apiPath = path.startsWith("/") ? path : `/${path}`;
  const response = await fetch(`${API_URL}${apiPath}`, { ...options, headers });
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new ApiError(response.status, data);
  }

  return data;
}

async function loadLevels() {
  const data = await request("/levels");
  levels.value = data.levels;
}

async function loadHistory() {
  const data = await request("/insults/history");
  history.value = data.history;
}

async function loadLeaderboard() {
  const params = new URLSearchParams({
    section: leaderboardSection.value,
    page: String(leaderboardPage.value),
    page_size: leaderboardSection.value === "top" ? "10" : "100",
  });
  const data = await request(`/leaderboard?${params.toString()}`);

  leaderboard.value = data.leaders;
  currentUserRank.value = data.current_user_rank;
}

async function loadPanels() {
  if (!isAuthed.value) {
    return;
  }

  panelLoading.value = true;

  try {
    await Promise.all([loadHistory(), loadLeaderboard()]);
  } catch (err) {
    error.value = handleApiError(err);
  } finally {
    panelLoading.value = false;
  }
}

async function submitAuth() {
  error.value = "";
  loading.value = true;

  try {
    const path = mode.value === "register" ? "/users/register" : "/users/login";
    const data = await request(path, {
      method: "POST",
      body: JSON.stringify({ username: username.value, password: password.value }),
    });

    rememberSession(data.token, data.user);
    await loadFight();
  } catch (err) {
    error.value = handleApiError(err);
  } finally {
    loading.value = false;
  }
}

async function startGame() {
  error.value = "";
  loading.value = true;
  activeView.value = "game";
  resetMonsterEffects();

  try {
    const data = await request("/games", { method: "POST" });
    game.value = data.game;
    pushEvent({
      type: "system",
      text: `Новый бой: ${data.game.monster.name}`,
      damage: null,
    });
  } catch (err) {
    error.value = handleApiError(err);
  } finally {
    loading.value = false;
  }
}

async function loadFight() {
  error.value = "";
  activeView.value = "game";
  resetMonsterEffects();

  try {
    await loadLevels();
    await startGame();

    if (game.value) {
      await loadPanels();
    }
  } catch (err) {
    error.value = handleApiError(err);
  }
}

async function submitInsult() {
  if (!game.value || loading.value || game.value.status !== "active" || !insult.value.trim()) {
    return;
  }

  error.value = "";
  loading.value = true;
  const text = insult.value.trim();

  try {
    const data = await request(`/games/${game.value.id}/insults`, {
      method: "POST",
      body: JSON.stringify({ text }),
    });

    game.value = data.game;
    insult.value = "";
    const damage = data.damage ?? 0;
    pushEvent({
      type: data.accepted && damage > 0 ? "hit" : data.accepted ? "no-damage" : "blocked",
      text,
      damage,
      score: data.score,
      reason: data.reason,
      reply: data.monster_reply,
      advancedTo: data.advanced_to_level_id,
    });
    playMonsterResponse(data);

    if (data.advanced_to_level_id) {
      user.value = {
        ...user.value,
        current_level_id: data.advanced_to_level_id,
        current_monster_hp: data.advanced_to_monster_hp,
      };
      localStorage.setItem("hui_user", JSON.stringify(user.value));
    } else if (data.accepted) {
      user.value = {
        ...user.value,
        current_monster_hp: data.game.monster.hp,
      };
      localStorage.setItem("hui_user", JSON.stringify(user.value));
    }

    if (data.accepted) {
      await loadPanels();
    }
  } catch (err) {
    if (err instanceof ApiError && err.data?.game) {
      game.value = err.data.game;
      pushEvent({
        type: "blocked",
        text,
        damage: 0,
        reason: err.data.reason || err.data.error,
        reply: err.data.monster_reply,
      });
    }

    error.value = handleApiError(err);
  } finally {
    loading.value = false;
  }
}

function humanError(code, data = {}) {
  const messages = {
    invalid_credentials: "Неверное имя игрока или пароль.",
    username_taken: "Это имя игрока уже занято.",
    username_too_short: "Имя игрока должно быть не короче 3 символов.",
    password_too_short: "Пароль должен быть не короче 6 символов.",
    authentication_required: "Войдите, чтобы продолжить.",
    invalid_token: "Сессия истекла. Войдите снова.",
    game_not_found: "Бой не найден.",
    game_already_finished: "Этот монстр уже побежден.",
    insult_required: "Введите обзывательство.",
    min_words: "Слишком коротко для этого монстра.",
    duplicate_insult: "Это обзывательство уже использовалось.",
    stale_game_session: "Этот бой устарел. Откройте текущего монстра.",
  };

  if (code === "rate_limit_exceeded") {
    const seconds = data.retry_after_seconds;
    return seconds
      ? `Слишком много запросов. Повторите через ${seconds} секунд.`
      : "Слишком много запросов. Повторите позже.";
  }

  if (code === "registration_ip_limit_exceeded") {
    const limit = data.limit || "несколько";
    return `С этого адреса уже создано ${limit} игрока за сутки. Попробуйте завтра.`;
  }

  return messages[code] || code;
}

function isAuthSessionError(err) {
  return err instanceof ApiError
    && err.status === 401
    && ["authentication_required", "invalid_token"].includes(err.data?.error);
}

function handleApiError(err) {
  if (isAuthSessionError(err)) {
    const message = humanError(err.data.error, err.data);
    clearSession();
    return message;
  }

  return humanError(err.message, err.data);
}

function countWords(text) {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function eventTitle(event) {
  if (event.type === "hit") {
    return `Попадание на ${event.damage}/10`;
  }

  if (event.type === "no-damage") {
    return "Фраза засчитана, но не сработала";
  }

  if (event.type === "system") {
    return "Бой";
  }

  const titles = {
    min_words: "Нужно больше слов",
    duplicate_insult: "Повтор не засчитан",
    stale_game_session: "Бой устарел",
    game_already_finished: "Монстр уже побежден",
  };

  return titles[event.reason] || "Без урона";
}

function eventDescription(event) {
  if (event.type === "hit") {
    return event.advancedTo
      ? `Монстр пал. Следующий уровень: ${event.advancedTo}.`
      : event.reply || "Монстр получил словесный урон.";
  }

  if (event.type === "no-damage") {
    return event.reply || "Монстр не получил урон.";
  }

  if (event.reason === "min_words") {
    return "Это обзывательство слишком короткое для правила уровня.";
  }

  if (event.reason === "duplicate_insult") {
    return "Этот игрок уже наносил урон такой фразой. Жизни монстра не изменились.";
  }

  if (event.reason === "stale_game_session") {
    return "Сохранен другой текущий бой. Обновите бой с текущим монстром.";
  }

  if (event.reason === "game_already_finished") {
    return "Переходите к следующему монстру.";
  }

  return event.reply || event.text;
}

async function openView(view) {
  activeView.value = view;

  try {
    if (view === "history") {
      await loadHistory();
    }

    if (view === "leaderboard") {
      await loadLeaderboard();
    }
  } catch (err) {
    error.value = handleApiError(err);
  }
}

async function setLeaderboardSection(section) {
  leaderboardSection.value = section;
  leaderboardPage.value = 1;

  try {
    await loadLeaderboard();
  } catch (err) {
    error.value = handleApiError(err);
  }
}

async function changeLeaderboardPage(delta) {
  leaderboardPage.value = Math.max(1, leaderboardPage.value + delta);

  try {
    await loadLeaderboard();
  } catch (err) {
    error.value = handleApiError(err);
  }
}

function useMonsterFallback(event) {
  if (event.target.dataset.fallbackApplied) {
    return;
  }

  event.target.dataset.fallbackApplied = "true";
  event.target.src = "/image.webp";
}

function clearMonsterTimers() {
  while (monsterTimers.length > 0) {
    window.clearTimeout(monsterTimers.pop());
  }
}

function resetMonsterEffects() {
  clearMonsterTimers();
  monsterHit.value = false;
  floatingDamage.value = null;
  monsterSpeech.value = "";
}

function playMonsterResponse(data) {
  clearMonsterTimers();
  monsterHit.value = false;
  floatingDamage.value = null;
  monsterSpeech.value = data.monster_reply || "";

  if (data.accepted && (data.damage ?? 0) > 0) {
    window.requestAnimationFrame(() => {
      monsterHit.value = true;
      floatingDamage.value = {
        id: `${Date.now()}-${data.damage ?? 0}`,
        damage: data.damage ?? 0,
      };
    });

    monsterTimers.push(window.setTimeout(() => {
      monsterHit.value = false;
    }, 420));
    monsterTimers.push(window.setTimeout(() => {
      floatingDamage.value = null;
    }, 900));
  }

  if (monsterSpeech.value) {
    monsterTimers.push(window.setTimeout(() => {
      monsterSpeech.value = "";
    }, 2600));
  }
}

onMounted(async () => {
  if (!isAuthed.value) {
    return;
  }

  await loadFight();
});

onBeforeUnmount(() => {
  clearMonsterTimers();
});
</script>

<template>
  <main class="app-shell">
    <section class="stage">
      <div v-if="!isAuthed" class="topbar">
        <div>
          <p class="eyebrow">Арена монстров</p>
          <h1>Победи монстра словами</h1>
        </div>
      </div>

      <div v-if="!isAuthed" class="auth-layout">
        <form class="auth-panel" @submit.prevent="submitAuth">
          <div class="tabs" role="tablist" aria-label="Режим входа">
            <button
              type="button"
              role="tab"
              :aria-selected="mode === 'login'"
              :class="{ active: mode === 'login' }"
              @click="mode = 'login'"
            >
              Вход
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="mode === 'register'"
              :class="{ active: mode === 'register' }"
              @click="mode = 'register'"
            >
              Регистрация
            </button>
          </div>

          <label>
            Имя игрока
            <input v-model="username" autocomplete="username" name="username" required />
          </label>
          <label>
            Пароль
            <input
              v-model="password"
              autocomplete="current-password"
              name="password"
              required
              type="password"
            />
          </label>

          <p v-if="error" class="error">{{ error }}</p>
          <button class="primary-button" :disabled="loading" type="submit">
            {{ loading ? "Работаем..." : mode === "register" ? "Создать игрока" : "Войти на арену" }}
          </button>
        </form>
      </div>

      <template v-else>
        <div v-if="activeView === 'game'" class="game-dashboard">
          <section class="fight">
            <div v-if="!game" class="empty-fight">
              <template v-if="error">
                <p class="error">{{ error }}</p>
                <button class="retry-fight primary-button" type="button" @click="loadFight">
                  Повторить
                </button>
              </template>
              <template v-else>
                Готовим бой...
              </template>
            </div>

            <template v-else>
              <div class="level-header">
                <p class="label">{{ currentLevel?.title || game.level_id }}</p>
                <h2>{{ currentLevel?.title || game.level_id }} · {{ game.monster.name }}</h2>
                <div class="level-meta">
                  <span>{{ currentLevel?.description }}</span>
                  <strong class="rule-pill">Минимум {{ requiredWords }} слов</strong>
                </div>
              </div>

              <div class="arena">
                <div class="monster-stage">
                  <div class="monster-art" :class="{ hit: monsterHit }">
                    <span class="monster-placeholder">фото монстра и игровой геймплей</span>
                    <img
                      :src="game.monster.icon"
                      :alt="game.monster.name"
                      @error="useMonsterFallback"
                    />
                    <Transition name="damage-pop">
                      <span
                        v-if="floatingDamage"
                        :key="floatingDamage.id"
                        class="floating-damage"
                      >
                        -{{ floatingDamage.damage }}
                      </span>
                    </Transition>
                  </div>
                  <div class="monster-status">
                    <div class="monster-info">
                      <strong>{{ game.monster.name }}</strong>
                      <span>Жизни {{ game.monster.hp }} / {{ game.monster.max_hp }}</span>
                    </div>

                    <div
                      class="hp-bar"
                      role="progressbar"
                      aria-label="Жизни монстра"
                      aria-valuemin="0"
                      :aria-valuemax="game.monster.max_hp"
                      :aria-valuenow="game.monster.hp"
                    >
                      <span :style="{ width: `${hpPercent}%` }"></span>
                    </div>
                  </div>
                  <Transition name="speech-pop">
                    <p v-if="monsterSpeech" class="monster-speech">{{ monsterSpeech }}</p>
                  </Transition>
                </div>

                <form class="insult-form" @submit.prevent="submitInsult">
                  <label>
                    <span class="field-top">
                      <span>Обзывательство</span>
                      <span class="word-counter" :class="{ met: wordRuleMet }">
                        {{ insultWordCount }} / {{ requiredWords }} слов
                      </span>
                    </span>
                    <textarea
                      v-model="insult"
                      :disabled="game.status !== 'active'"
                      :placeholder="`Минимум ${requiredWords} слов. Абсурднее — лучше.`"
                      rows="4"
                      @keydown.enter.exact.prevent="submitInsult"
                    ></textarea>
                  </label>
                  <div class="action-row">
                    <p v-if="error" class="error">{{ error }}</p>
                    <button
                      class="primary-button"
                      :disabled="loading || game.status !== 'active' || !insult.trim()"
                      type="submit"
                    >
                      Ударить словом
                    </button>
                  </div>
                </form>
              </div>

              <div v-if="game.status === 'won'" class="victory-band">
                <strong>Монстр побежден.</strong>
                <button class="ghost-button" type="button" @click="startGame">
                  К следующему монстру
                </button>
              </div>
            </template>
          </section>

          <aside class="score-history">
            <div class="stats-panel">
              <div class="player-strip">
                <span>{{ user?.username }}</span>
                <button class="logout-button inline-link-button" type="button" @click="logout">
                  Выйти
                </button>
              </div>
              <div class="score-total">
                <p>Всего очков</p>
                <strong>{{ totalDamage }}</strong>
                <span>{{ totalInsults }} обзывательств</span>
              </div>
            </div>

            <div class="side-actions">
              <button class="rank-tab" type="button" @click="openView('leaderboard')">
                Место в лидерборде
                <strong v-if="currentUserRank">#{{ currentUserRank.rank }}</strong>
              </button>
              <button class="ghost-button" type="button" @click="openView('leaderboard')">
                Лидерборд
              </button>
            </div>

            <div class="panel-heading">
              <p>История обзывательств</p>
              <button class="inline-link-button" type="button" @click="openView('history')">
                Вся история
              </button>
              <span v-if="panelLoading">Загрузка</span>
            </div>
            <div v-if="recentHistory.length === 0" class="empty-history">
              Пока нет принятых обзывательств.
            </div>
            <article v-for="item in recentHistory" :key="item.id" class="event-card">
              <div class="event-top">
                <strong>{{ item.damage }}/10</strong>
                <small>{{ item.monster_name || item.level_id || "Неизвестный монстр" }}</small>
              </div>
              <p class="event-text">{{ item.text }}</p>
            </article>

            <div class="panel-heading panel-heading-compact">
              <p>Журнал боя</p>
            </div>
            <section class="combat-log side-combat-log" aria-live="polite" aria-label="Журнал боя">
              <article
                v-for="event in events"
                :key="event.id"
                class="combat-event"
                :class="event.type"
              >
                <div>
                  <strong>{{ eventTitle(event) }}</strong>
                  <p>{{ eventDescription(event) }}</p>
                </div>
                <span v-if="event.damage !== null && event.damage !== undefined">
                  {{ event.damage }} урона
                </span>
              </article>
              <p v-if="events.length === 0" class="combat-empty">
                Журнал боя появится после первого обзывательства.
              </p>
            </section>
          </aside>
        </div>

        <section v-else-if="activeView === 'history'" class="full-view">
          <div class="view-header">
            <button class="ghost-button" type="button" @click="openView('game')">
              Назад к игре
            </button>
            <div>
              <p class="label">Принятые обзывательства</p>
              <h2>Полная история</h2>
            </div>
            <div class="view-stat">
              <strong>{{ totalDamage }}</strong>
              <span>{{ totalInsults }} обзывательств</span>
            </div>
          </div>

          <div v-if="history.length === 0" class="empty-state">Пока нет принятых обзывательств.</div>
          <div v-else class="history-list">
            <article v-for="item in history" :key="item.id" class="history-row">
              <div>
                <p class="event-text">{{ item.text }}</p>
                <small>{{ item.monster_name || item.level_id || "Неизвестный монстр" }}</small>
              </div>
              <div class="score-badges">
                <span>{{ item.damage }}/10 урона</span>
                <span>{{ item.score?.source || "неизвестно" }}</span>
                <span v-if="item.score?.toxic" class="toxic">
                  {{ item.score.label || "токсично" }}
                </span>
              </div>
            </article>
          </div>
        </section>

        <section v-else class="full-view">
          <div class="view-header">
            <button class="ghost-button" type="button" @click="openView('game')">
              Назад к игре
            </button>
            <div>
              <p class="label">Лидерборд</p>
              <h2>Рейтинг игроков</h2>
            </div>
            <div v-if="currentUserRank" class="view-stat">
              <strong>#{{ currentUserRank.rank }}</strong>
              <span>Твоё место</span>
            </div>
          </div>

          <div class="leaderboard-switch" role="tablist" aria-label="Раздел лидерборда">
            <button
              type="button"
              role="tab"
              :aria-selected="leaderboardSection === 'top'"
              :class="{ active: leaderboardSection === 'top' }"
              @click="setLeaderboardSection('top')"
            >
              Топ 10
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="leaderboardSection === 'all'"
              :class="{ active: leaderboardSection === 'all' }"
              @click="setLeaderboardSection('all')"
            >
              Все игроки
            </button>
          </div>

          <article v-if="currentUserRank" class="your-rank">
            <span>Твоё место</span>
            <strong>#{{ currentUserRank.rank }}</strong>
            <small>
              {{ currentUserRank.total_damage }} урона /
              {{ currentUserRank.insults_count }} обзывательств
            </small>
          </article>

          <div v-if="leaderboard.length === 0" class="empty-state">Пока нет игроков.</div>
          <div v-else class="leaderboard-list">
            <article
              v-for="leader in leaderboard"
              :key="leader.username"
              class="leader-row"
              :class="{ current: leader.username === user?.username }"
            >
              <strong>#{{ leader.rank }}</strong>
              <div>
                <p>{{ leader.username }}</p>
                <small>{{ leader.current_level_id }}</small>
              </div>
              <span>{{ leader.total_damage }}</span>
            </article>
          </div>

          <div v-if="leaderboardSection === 'all'" class="pager">
            <button
              class="ghost-button"
              type="button"
              :disabled="leaderboardPage === 1"
              @click="changeLeaderboardPage(-1)"
            >
              Назад
            </button>
            <span>Страница {{ leaderboardPage }}</span>
            <button
              class="ghost-button"
              type="button"
              :disabled="leaderboard.length < 100"
              @click="changeLeaderboardPage(1)"
            >
              Далее
            </button>
          </div>
        </section>
      </template>
    </section>
  </main>
</template>

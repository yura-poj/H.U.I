<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:5001/api";
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
const totalDamage = computed(() => history.value.reduce((sum, item) => sum + item.damage, 0));
const totalInsults = computed(() => history.value.length);
const recentHistory = computed(() => history.value.slice(0, RECENT_HISTORY_LIMIT));

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

function pushEvent(entry) {
  events.value = [entry, ...events.value].slice(0, 8);
}

async function request(path, options = {}) {
  const headers = {
    ...(options.body ? { "Content-Type": "application/json" } : {}),
    ...(token.value ? { Authorization: `Bearer ${token.value}` } : {}),
    ...options.headers,
  };

  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.error || `request_failed_${response.status}`);
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
    error.value = humanError(err.message);
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
    activeView.value = "game";
    await loadLevels();
    await startGame();
    await loadPanels();
  } catch (err) {
    error.value = humanError(err.message);
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
      text: `New fight: ${data.game.monster.name}`,
      damage: null,
    });
  } catch (err) {
    error.value = humanError(err.message);
  } finally {
    loading.value = false;
  }
}

async function submitInsult() {
  if (!game.value || !insult.value.trim()) {
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
    pushEvent({
      type: data.accepted ? "hit" : "blocked",
      text,
      damage: data.damage,
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
    error.value = humanError(err.message);
  } finally {
    loading.value = false;
  }
}

function humanError(code) {
  const messages = {
    invalid_credentials: "Wrong username or password.",
    username_taken: "This username is already taken.",
    username_too_short: "Username must be at least 3 characters.",
    password_too_short: "Password must be at least 6 characters.",
    authentication_required: "Log in to continue.",
    invalid_token: "Session expired. Log in again.",
    game_not_found: "Game was not found.",
    game_already_finished: "This monster is already defeated.",
  };

  return messages[code] || code;
}

async function openView(view) {
  activeView.value = view;

  if (view === "history") {
    await loadHistory();
  }

  if (view === "leaderboard") {
    await loadLeaderboard();
  }
}

async function setLeaderboardSection(section) {
  leaderboardSection.value = section;
  leaderboardPage.value = 1;
  await loadLeaderboard();
}

async function changeLeaderboardPage(delta) {
  leaderboardPage.value = Math.max(1, leaderboardPage.value + delta);
  await loadLeaderboard();
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

  if (data.accepted) {
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

  try {
    await loadLevels();
    await startGame();
    await loadPanels();
  } catch (err) {
    error.value = humanError(err.message);
  }
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
          <p class="eyebrow">Monster insult arena</p>
          <h1>Break the monster with words</h1>
        </div>
      </div>

      <div v-if="!isAuthed" class="auth-layout">
        <form class="auth-panel" @submit.prevent="submitAuth">
          <div class="tabs" role="tablist" aria-label="Authentication mode">
            <button
              type="button"
              :class="{ active: mode === 'login' }"
              @click="mode = 'login'"
            >
              Login
            </button>
            <button
              type="button"
              :class="{ active: mode === 'register' }"
              @click="mode = 'register'"
            >
              Register
            </button>
          </div>

          <label>
            Username
            <input v-model="username" autocomplete="username" name="username" required />
          </label>
          <label>
            Password
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
            {{ loading ? "Working..." : mode === "register" ? "Create player" : "Enter arena" }}
          </button>
        </form>
      </div>

      <template v-else>
        <div v-if="activeView === 'game'" class="game-dashboard">
          <aside class="stats-panel">
            <div class="score-total">
              <p>Всего очков</p>
              <strong>{{ totalDamage }}</strong>
              <span>{{ totalInsults }} обзывательств</span>
            </div>
          </aside>

          <section class="fight">
            <div v-if="!game" class="empty-fight">
              Готовим бой...
            </div>

            <template v-else>
              <div class="level-header">
                <p class="label">{{ currentLevel?.title || game.level_id }}</p>
                <h2>Описание уровня</h2>
                <p>{{ currentLevel?.description }}</p>
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
                  <Transition name="speech-pop">
                    <p v-if="monsterSpeech" class="monster-speech">{{ monsterSpeech }}</p>
                  </Transition>
                </div>

                <div class="monster-info">
                  <strong>{{ game.monster.name }}</strong>
                  <span>HP {{ game.monster.hp }} / {{ game.monster.max_hp }}</span>
                </div>

                <div class="hp-bar" aria-label="Monster HP">
                  <span :style="{ width: `${hpPercent}%` }"></span>
                </div>

                <form class="insult-form" @submit.prevent="submitInsult">
                  <label>
                    Обзывательство
                    <textarea
                      v-model="insult"
                      :disabled="game.status !== 'active'"
                      :placeholder="`At least ${game.rules.min_words_per_insult} words`"
                      rows="4"
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
                <strong>Monster defeated.</strong>
                <button class="ghost-button" type="button" @click="startGame">Next fight</button>
              </div>
            </template>
          </section>

          <aside class="score-history">
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
              <p>История с очками</p>
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
                <small>{{ item.monster_name || item.level_id || "Unknown monster" }}</small>
              </div>
              <p class="event-text">{{ item.text }}</p>
            </article>
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
                <small>{{ item.monster_name || item.level_id || "Unknown monster" }}</small>
              </div>
              <div class="score-badges">
                <span>{{ item.damage }}/10 урона</span>
                <span>{{ item.score?.source || "unknown" }}</span>
                <span v-if="item.score?.toxic" class="toxic">
                  {{ item.score.label || "toxic" }}
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

          <div class="leaderboard-switch">
            <button
              type="button"
              :class="{ active: leaderboardSection === 'top' }"
              @click="setLeaderboardSection('top')"
            >
              Топ 10
            </button>
            <button
              type="button"
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
            <article v-for="leader in leaderboard" :key="leader.username" class="leader-row">
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

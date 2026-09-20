/**
 * OX Mining — Frontend JS
 * Handles: Telegram Auth, Mining, Ads, Referrals, Daily, Tasks, Leaderboard, Withdrawal
 */

// ============================================================
// CONFIG
// ============================================================
const API_BASE = '/api/v1';

// ============================================================
// STATE
// ============================================================
const state = {
  user: null,
  balance: null,
  miningStatus: null,
  token: null,
  authReady: false,
  activeScreen: 'mine',
  miningTimer: null,
  miningStatusRequest: null,
  referralLink: '',
  boostPlans: [],
  adCooldown: 0,
  adCooldownTimer: null,
  preloadedAdId: null,
  withdrawal: { minimumCoins: 500000, feePercent: 5, coinValueBdt: 0.001 },
};
const taskTargets = {};

// ============================================================
// TELEGRAM WEBAPP SDK
// ============================================================
const tg = window.Telegram?.WebApp;

function initTelegramApp() {
  if (tg) {
    tg.ready();
    tg.expand();
    tg.setHeaderColor('#0a0b0f');
    tg.setBackgroundColor('#0a0b0f');
  }
}

// ============================================================
// API HELPERS
// ============================================================
async function apiCall(endpoint, method = 'GET', body = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;

  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  try {
    console.log(`[API] ${method} ${API_BASE}${endpoint}`);
    const res = await fetch(`${API_BASE}${endpoint}`, opts);
    const text = await res.text();
    let data;
    try {
      data = text ? JSON.parse(text) : {};
    } catch (jsonError) {
      console.error('[API] Invalid JSON:', text);
      const detail = text.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 120);
      return {
        ok: false,
        status: res.status,
        data: {
          error: detail
            ? `Server error ${res.status}: ${detail}`
            : `Server returned an invalid response (${res.status}). Please try again.`,
        },
      };
    }
    console.log(`[API] ${res.status}`, data);
    if (res.status === 401 && !endpoint.startsWith('/auth/')) {
      state.token = null;
      state.authReady = false;
      localStorage.removeItem('auth_token');
    }
    return { ok: res.ok, status: res.status, data };
  } catch (err) {
    console.error('[API] Network error:', err);
    return { ok: false, status: 0, data: { error: 'Network error. Please check server.' } };
  }
}

// ============================================================
// AUTH
// ============================================================
async function authenticate() {
  const initData = tg?.initData || '';
  // start_param contains the referral code directly (e.g., "ref_12345_abc123")
  const refCode = tg?.initDataUnsafe?.start_param || '';

  // In dev mode without Telegram, use a mock
  if (!initData && window.location.hostname === 'localhost') {
    console.warn('[DEV] No initData found. Using dev mock authentication.');
    const cached = localStorage.getItem('auth_token');
    if (cached) {
      state.token = cached;
      const res = await apiCall('/me');
      if (res.ok) {
        state.user = res.data.user;
        state.authReady = true;
        hideLoader();
        renderApp();
        return;
      }
    }
    // Auto-login with test endpoint
    const res = await apiCall('/auth/test', 'POST', { telegram_id: 999999999, first_name: 'Dev', username: 'devuser' });
    if (res.ok) {
      state.token = res.data.token;
      state.user = res.data.user;
      state.authReady = true;
      localStorage.setItem('auth_token', state.token);
    }
    hideLoader();
    renderApp();
    return;
  }

  const res = await apiCall('/auth/telegram', 'POST', {
    initData,
    referral_code: refCode,
  });

  if (res.ok) {
    state.token = res.data.token;
    state.user = res.data.user;
    state.authReady = true;
    localStorage.setItem('auth_token', state.token);
    hideLoader();
    renderApp();
  } else {
    state.token = null;
    state.authReady = false;
    localStorage.removeItem('auth_token');
    showToast('Authentication failed. Please restart the app.', 'error');
    setTimeout(() => hideLoader(), 2000);
  }
}

// ============================================================
// RENDER APP
// ============================================================
function renderApp() {
  renderHeader();
  showScreen('mine');
  loadBalance();
  preloadRewardedAd();
  
  // Show admin button if user is admin
  if (state.user && state.user.is_admin) {
    const addTaskBtn = document.getElementById('btn-add-task');
    if (addTaskBtn) addTaskBtn.style.display = 'flex';
  }
}

function renderHeader() {
  const u = state.user;
  if (u?.photo_url) {
    document.getElementById('user-avatar').src = u.photo_url;
  }
}

// ============================================================
// SCREEN NAVIGATION
// ============================================================
function showScreen(screenName) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  const screen = document.getElementById(`screen-${screenName}`);
  const navItem = document.querySelector(`[data-screen="${screenName}"]`);
  if (screen) screen.classList.add('active');
  if (navItem) navItem.classList.add('active');

  state.activeScreen = screenName;

  // Lazy load screen data
  if (!state.token) return;
  if (screenName === 'mine') loadMiningStatus();
  if (screenName === 'boost') loadBoostPlans();
  if (screenName === 'referral') loadReferrals();
  if (screenName === 'tasks') loadTasks();
  if (screenName === 'leaderboard') loadLeaderboard();
  if (screenName === 'profile') loadProfile();
  if (screenName === 'withdraw') loadWithdrawalInfo();
}

async function loadProfile() {
  const errorEl = document.getElementById('profile-error');
  if (errorEl) errorEl.style.display = 'none';

  const res = await apiCall('/me');
  if (!res.ok) {
    if (errorEl) {
      errorEl.textContent = res.data?.error || `Failed to load profile (${res.status})`;
      errorEl.style.display = 'block';
    }
    return;
  }

  const user = res.data?.user || {};
  const balance = res.data?.balance || {};
  const profileAvatar = document.getElementById('profile-avatar');
  if (profileAvatar) profileAvatar.src = user.photo_url || document.getElementById('user-avatar')?.src || '';

  document.getElementById('profile-name').textContent = [user.first_name, user.last_name].filter(Boolean).join(' ') || 'Anonymous';
  const handle = user.username ? `@${user.username.replace(/^@/, '')}` : `ID: ${user.telegram_id || 'Unknown'}`;
  document.getElementById('profile-username').textContent = handle;
  document.getElementById('profile-id').textContent = user.telegram_id ? `Telegram ID: ${user.telegram_id}` : '';
  document.getElementById('profile-available').textContent = formatCoinsExact(balance.available_coins || 0);
  document.getElementById('profile-pending').textContent = formatCoinsExact(balance.pending_coins || 0);
  document.getElementById('profile-mined').textContent = formatCoinsExact(balance.mined_coins_total || 0);
  document.getElementById('profile-rate').textContent = `${formatCoinsExact(balance.effective_rate || balance.mining_rate || 0)} / hour`;
}

// ============================================================
// BALANCE
// ============================================================
async function loadBalance() {
  const res = await apiCall('/me/balance');
  if (res.ok) {
    state.balance = res.data;
    updateBalanceDisplay(res.data.available_coins);
  }
}

function updateBalanceDisplay(coins) {
  const el = document.getElementById('balance-amount');
  if (el) {
    animateNumber(el, parseInt(el.dataset.value || '0'), coins);
    el.dataset.value = coins;
  }
}

function animateNumber(el, from, to) {
  const duration = 600;
  const start = performance.now();
  function step(now) {
    const progress = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    const current = Math.floor(from + (to - from) * ease);
    el.textContent = formatCoins(current);
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function formatCoins(n) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(2) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K';
  return n.toLocaleString();
}

function formatCoinsExact(n) {
  return n.toLocaleString();
}

// ============================================================
// MINING
// ============================================================
async function loadMiningStatus() {
  if (state.miningStatusRequest) return state.miningStatusRequest;

  state.miningStatusRequest = (async () => {
    const res = await apiCall('/mining/status');
    if (!res.ok) return res;

    state.miningStatus = res.data;
    renderMiningUI(res.data);

    // Start live countdown timer
    if (state.miningTimer) clearInterval(state.miningTimer);
    if (res.data.is_mining && !res.data.session_full) {
      state.miningTimer = setInterval(() => tickMining(), 1000);
    }
    return res;
  })();

  try {
    return await state.miningStatusRequest;
  } finally {
    state.miningStatusRequest = null;
  }
}

function tickMining() {
  if (!state.miningStatus || !state.miningStatus.is_mining) return;
  const rate = state.miningStatus.mining_rate;
  const maxSec = 8 * 3600;

  state.miningStatus.session_elapsed_seconds = Math.min(
    state.miningStatus.session_elapsed_seconds + 1,
    maxSec
  );
  state.miningStatus.earned_this_session = Math.floor(
    state.miningStatus.session_elapsed_seconds * rate / 3600
  );
  state.miningStatus.session_remaining_seconds = Math.max(
    0, maxSec - state.miningStatus.session_elapsed_seconds
  );
  state.miningStatus.session_full = state.miningStatus.session_remaining_seconds === 0;

  renderMiningProgress(state.miningStatus);
}

function renderMiningUI(data) {
  const orb = document.getElementById('mining-orb');
  const orbLabel = document.getElementById('orb-label');

  if (data.is_mining) {
    orb?.classList.add('active');
    if (orbLabel) orbLabel.textContent = data.session_full ? 'FULL!' : 'MINING';
  } else {
    orb?.classList.remove('active');
    if (orbLabel) orbLabel.textContent = 'TAP START';
  }

  // Mining rate badge
  const rateBadge = document.getElementById('mining-rate-badge');
  if (rateBadge) rateBadge.textContent = `+${data.mining_rate} OX / hour`;

  renderMiningProgress(data);
  renderMiningButtons(data);
}

function renderMiningProgress(data) {
  const progressFill = document.getElementById('progress-fill');
  const progressTime = document.getElementById('progress-time');
  const earnedEl = document.getElementById('earned-this-session');

  const pct = data.is_mining
    ? (data.session_elapsed_seconds / (8 * 3600)) * 100
    : 0;

  if (progressFill) progressFill.style.width = `${Math.min(pct, 100)}%`;

  if (progressTime) {
    if (data.is_mining && !data.session_full) {
      progressTime.textContent = formatTime(data.session_remaining_seconds) + ' remaining';
    } else if (data.session_full) {
      progressTime.textContent = '🔔 Session full — Claim now!';
    } else {
      progressTime.textContent = 'Start mining to earn OX';
    }
  }

  if (earnedEl) {
    earnedEl.textContent = data.is_mining ? `+${formatCoins(data.earned_this_session || 0)} OX` : '--';
  }
}

function renderMiningButtons(data) {
  const startBtn = document.getElementById('btn-start-mining');
  const claimBtn = document.getElementById('btn-claim-mining');

  if (startBtn) {
    startBtn.style.display = data.is_mining ? 'none' : 'flex';
  }
  if (claimBtn) {
    claimBtn.style.display = data.is_mining ? 'flex' : 'none';
    claimBtn.disabled = !data.can_claim;
  }
}

async function startMining() {
  const btn = document.getElementById('btn-start-mining');
  btn.disabled = true;

  const res = await apiCall('/mining/start', 'POST');
  if (res.ok) {
    showToast('⛏️ Mining started!', 'success');
    await loadMiningStatus();
  } else {
    showToast(res.data.error || 'Failed to start mining', 'error');
  }
  btn.disabled = false;
}

async function claimMining() {
  const btn = document.getElementById('btn-claim-mining');
  btn.disabled = true;
  btn.textContent = 'Claiming...';

  const res = await apiCall('/mining/claim', 'POST');
  if (res.ok) {
    showToast(`✅ Claimed ${formatCoins(res.data.coins_earned)} OX!`, 'success');
    updateBalanceDisplay(res.data.new_balance);
    if (state.miningTimer) clearInterval(state.miningTimer);
    await loadMiningStatus();
  } else {
    showToast(res.data.error || 'Claim failed', 'error');
  }
  btn.disabled = false;
  btn.textContent = '⛏️ Claim Coins';
}

// ============================================================
// BOOST PLANS
// ============================================================
async function loadBoostPlans() {
  const res = await apiCall('/boosts');
  if (!res.ok) {
    const container = document.getElementById('boost-plans-grid');
    if (container) {
      container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><div class="empty-state-text">${res.data?.error || 'Please authenticate first'}</div></div>`;
    }
    return;
  }

  state.boostPlans = res.data.plans;
  renderBoostPlans(res.data.plans);
}

function renderBoostPlans(plans) {
  const container = document.getElementById('boost-plans-grid');
  if (!container) return;

  container.innerHTML = plans.map(p => `
    <div class="boost-plan-card ${p.name}" onclick="buyBoost(${p.id}, '${p.name}', ${p.price_stars})">
      <div class="boost-plan-emoji">${p.emoji}</div>
      <div class="boost-plan-name">${p.display_name}</div>
      <div class="boost-plan-rate">${p.mining_rate}</div>
      <div class="boost-plan-unit">OX / hour</div>
      ${p.price_stars === 0
        ? `<div class="boost-plan-free">Free</div>`
        : `<div class="boost-plan-price">⭐ ${p.price_stars} Stars</div>
           <div class="boost-plan-duration">${p.duration_days} days</div>`
      }
    </div>
  `).join('');
}

async function buyBoost(planId, planName, priceStars) {
  if (priceStars === 0) {
    showToast('This is your current free plan', 'error');
    return;
  }

  if (!state.authReady || !state.token) {
    showToast('Please authenticate before purchasing', 'error');
    return;
  }

  const telegramWebApp = window.Telegram?.WebApp;
  if (!telegramWebApp?.openInvoice) {
    showToast('Please open in Telegram to purchase', 'error');
    return;
  }

  showToast(`Initiating ⭐${priceStars} Stars payment...`);
  const res = await apiCall(`/boosts/${planId}/invoice`, 'POST');
  if (!res.ok || !res.data?.invoice_url) {
    showToast(res.data?.error || 'Could not start payment', 'error');
    return;
  }

  telegramWebApp.openInvoice(res.data.invoice_url, (status) => {
    if (status === 'paid') {
      showToast(`${planName} boost activated!`, 'success');
      loadBoostPlans();
      loadMiningStatus();
    } else if (status === 'failed') {
      showToast('Payment failed', 'error');
    }
  });
}

// ============================================================
// ADS (Monetag)
// ============================================================
function createAdEventId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  return `ad_${Date.now()}_${Math.random().toString(36).slice(2)}`;
}

function getRewardedAdFunction() {
  return window.show_11824725;
}

async function preloadRewardedAd() {
  const showAd = getRewardedAdFunction();
  if (typeof showAd !== 'function') return;

  const eventId = createAdEventId();
  try {
    await showAd({ type: 'preload', ymid: eventId });
    state.preloadedAdId = eventId;
  } catch (error) {
    console.warn('[ADS] Preload failed:', error);
  }
}

async function watchAd() {
  if (state.adCooldown > 0) {
    showToast(`Wait ${state.adCooldown}s before next ad`, 'error');
    return;
  }

  const showAd = getRewardedAdFunction();
  if (typeof showAd !== 'function') {
    showToast('Ad is still loading. Please try again.', 'error');
    return;
  }

  const eventId = state.preloadedAdId || createAdEventId();
  state.preloadedAdId = null;
  showToast('Loading ad...');

  try {
    await showAd({ ymid: eventId });
    const res = await apiCall('/ads/reward', 'POST', {
      ad_event_id: eventId,
      ad_type: 'rewarded_interstitial',
    });
    if (res.ok) {
      showToast(`🎬 +${res.data.coins_earned} OX!`, 'success');
      updateBalanceDisplay(res.data.new_balance);
      startAdCooldown(5 * 60);
      preloadRewardedAd();
    } else {
      showToast(res.data.error || 'Ad reward failed', 'error');
    }
  } catch (error) {
    console.warn('[ADS] Ad failed or skipped:', error);
    showToast('Ad failed or was skipped', 'error');
  }
}

async function simulateDevAdReward() {
  showToast('🎬 Simulating ad...', 'success');
  setTimeout(async () => {
    const fakeEventId = `dev_ad_${Date.now()}`;
    const res = await apiCall('/ads/reward', 'POST', {
      ad_event_id: fakeEventId,
      ad_type: 'rewarded_interstitial',
    });
    if (res.ok) {
      showToast(`+${res.data.coins_earned} OX!`, 'success');
      updateBalanceDisplay(res.data.new_balance);
      startAdCooldown(30); // shorter cooldown in dev
    } else {
      showToast(res.data.error || 'Ad failed', 'error');
    }
  }, 1500);
}

function startAdCooldown(seconds) {
  state.adCooldown = seconds;
  const btn = document.getElementById('btn-watch-ad');
  if (!btn) return;

  if (state.adCooldownTimer) clearInterval(state.adCooldownTimer);
  state.adCooldownTimer = setInterval(() => {
    state.adCooldown--;
    if (btn) btn.textContent = `🎬 Watch Ad (${state.adCooldown}s)`;
    if (state.adCooldown <= 0) {
      clearInterval(state.adCooldownTimer);
      if (btn) btn.textContent = '🎬 Watch Ad +100';
    }
  }, 1000);
}

// ============================================================
// REFERRAL
// ============================================================
async function loadReferrals() {
  const linkEl = document.getElementById('referral-link-text');
  const res = await apiCall('/referrals/stats');
  if (!res.ok) {
    if (linkEl) linkEl.textContent = res.data?.error || 'Unable to load referral link';
    return;
  }

  const data = res.data;
  state.referralLink = data.referral_link;

  const totalEl = document.getElementById('ref-total');
  const qualEl = document.getElementById('ref-qualified');
  const earnedEl = document.getElementById('ref-earned');

  if (linkEl) linkEl.textContent = data.referral_link;
  if (totalEl) totalEl.textContent = data.total_referrals;
  if (qualEl) qualEl.textContent = data.qualified_referrals;
  if (earnedEl) earnedEl.textContent = formatCoins(data.total_earned);
}

async function copyReferralLink() {
  try {
    await navigator.clipboard.writeText(state.referralLink);
    const btn = document.getElementById('copy-ref-btn');
    if (btn) {
      btn.textContent = '✅ Copied!';
      btn.classList.add('copied');
      setTimeout(() => {
        btn.textContent = '📋 Copy';
        btn.classList.remove('copied');
      }, 2000);
    }
  } catch {
    showToast('Copy failed', 'error');
  }
}

function shareReferralLink() {
  if (tg) {
    tg.openTelegramLink(
      `https://t.me/share/url?url=${encodeURIComponent(state.referralLink)}&text=${encodeURIComponent('🐂 Join me on OX Mining and earn OX!')}`
    );
  } else {
    copyReferralLink();
  }
}

// ============================================================
// DAILY REWARD
// ============================================================
async function loadDailyReward() {
  const res = await apiCall('/rewards/daily');
  if (!res.ok) return;

  const data = res.data;
  const SCHEDULE = { 1: 100, 2: 150, 3: 200, 4: 300, 5: 400, 6: 600, 7: 1000 };

  const grid = document.getElementById('daily-grid');
  if (grid) {
    grid.innerHTML = Object.entries(SCHEDULE).map(([day, coins]) => {
      const dayNum = parseInt(day);
      const isClaimed = dayNum < data.current_streak || (dayNum === data.current_streak && !data.can_claim_today);
      const isToday = dayNum === (data.current_streak + (data.can_claim_today ? 1 : 0));
      return `
        <div class="daily-day ${isClaimed ? 'claimed' : ''} ${isToday ? 'today' : ''}">
          <div class="daily-day-num">Day ${day}</div>
          ${isClaimed
            ? `<div class="daily-day-check">✅</div>`
            : `<div class="daily-day-coins">+${coins}</div>`
          }
        </div>
      `;
    }).join('');
  }

  const claimBtn = document.getElementById('btn-daily-claim');
  if (claimBtn) {
    claimBtn.disabled = !data.can_claim_today;
    claimBtn.textContent = data.can_claim_today ? '🎁 Claim Daily Reward' : '✅ Claimed Today';
  }

  const streakEl = document.getElementById('daily-streak');
  if (streakEl) streakEl.textContent = `🔥 ${data.current_streak} day streak`;
}

async function claimDailyReward() {
  const btn = document.getElementById('btn-daily-claim');
  btn.disabled = true;

  const res = await apiCall('/rewards/daily', 'POST');
  if (res.ok) {
    showToast(`🎁 Day ${res.data.day}: +${formatCoins(res.data.coins_earned)} OX!`, 'success');
    updateBalanceDisplay(res.data.new_balance);
    loadDailyReward();
  } else {
    showToast(res.data.error || 'Claim failed', 'error');
    btn.disabled = false;
  }
}

// ============================================================
// TASKS
// ============================================================
async function loadTasks() {
  const container = document.getElementById('task-list');
  if (!container) return;

  container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⏳</div><div class="empty-state-text">Loading tasks...</div></div>`;

  try {
    const res = await apiCall('/tasks');
    console.log('[TASKS] API response:', res);

    if (!res.ok) {
      container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">⚠️</div><div class="empty-state-text">${res.data?.error || `Failed to load tasks (${res.status})`}</div></div>`;
      return;
    }

    const tasks = Array.isArray(res.data?.tasks) ? res.data.tasks : [];
    Object.keys(taskTargets).forEach(key => delete taskTargets[key]);
    tasks.forEach(task => { taskTargets[task.id] = task.target_url || ''; });

    const ICONS = {
      JOIN_CHANNEL: '📢', JOIN_GROUP: '👥', FOLLOW: '⭐',
      VISIT_WEBSITE: '🌐', PLAY_GAME: '🎮', DAILY_LOGIN: '📅', INVITE_FRIEND: '👥',
    };

    if (tasks.length === 0) {
      container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">📋</div><div class="empty-state-text">No tasks available yet</div></div>`;
      return;
    }

    container.innerHTML = tasks.map(task => `
      <div class="task-row ${task.user_status === 'COMPLETED' ? 'completed' : ''}">
        <div class="task-icon">${ICONS[task.task_type] || '✅'}</div>
        <div class="task-info">
          <div class="task-title">${task.display_name || task.name || 'Task'}</div>
          <div class="task-reward">+${formatCoins(task.reward_coins || 0)} OX</div>
        </div>
        <div class="task-action">
          ${task.user_status === 'COMPLETED'
            ? `<span class="badge badge-green">Done</span>`
            : `<button class="btn btn-primary btn-sm" onclick="openTask(${task.id})">${task.target_url ? '→ Go' : 'Claim'}</button>`
          }
        </div>
      </div>
    `).join('');

  } catch (error) {
    console.error('[TASKS] Error:', error);
    container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">❌</div><div class="empty-state-text">Failed to load tasks</div></div>`;
  }
}

function openTask(taskId) {
  const targetUrl = taskTargets[taskId];
  if (targetUrl) {
    try {
      const parsedUrl = new URL(targetUrl, window.location.origin);
      if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
        showToast('Invalid task link', 'error');
        return;
      }
      if (tg?.openLink) tg.openLink(parsedUrl.href);
      else window.open(parsedUrl.href, '_blank', 'noopener,noreferrer');
    } catch (error) {
      showToast('Invalid task link', 'error');
      return;
    }
  }
  completeTask(taskId);
}

async function completeTask(taskId) {
  const res = await apiCall(`/tasks/${taskId}/complete`, 'POST');
  if (res.ok) {
    showToast(`✅ +${formatCoins(res.data.coins_earned)} OX!`, 'success');
    updateBalanceDisplay(res.data.new_balance);
    loadTasks();
  } else {
    showToast(res.data.error || 'Task failed', 'error');
  }
}

function openAddTaskModal() {
  document.getElementById('add-task-modal').style.display = 'flex';
}

function closeAddTaskModal() {
  document.getElementById('add-task-modal').style.display = 'none';
  document.getElementById('task-name').value = '';
  document.getElementById('task-display-name').value = '';
  document.getElementById('task-reward').value = '';
  document.getElementById('task-description').value = '';
  document.getElementById('task-url').value = '';
  document.getElementById('task-repeatable').checked = false;
  document.getElementById('task-active').checked = true;
}

async function submitAddTask(btn) {
  const name = document.getElementById('task-name').value.trim();
  const displayName = document.getElementById('task-display-name').value.trim();
  const taskType = document.getElementById('task-type').value;
  const reward = parseInt(document.getElementById('task-reward').value || '0');
  const description = document.getElementById('task-description').value.trim();
  const url = document.getElementById('task-url').value.trim();
  const repeatable = document.getElementById('task-repeatable').checked;
  const active = document.getElementById('task-active').checked;

  if (!name || !displayName || !reward) {
    showToast('Fill required fields', 'error');
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Creating...';

  const res = await apiCall('/tasks', 'POST', {
    name,
    display_name: displayName,
    task_type: taskType,
    reward_coins: reward,
    description: description || undefined,
    target_url: url || undefined,
    is_repeatable: repeatable,
    is_active: active,
  });

  if (res.ok) {
    showToast('✅ Task created!', 'success');
    closeAddTaskModal();
    loadTasks();
  } else {
    showToast(res.data.error || 'Failed to create task', 'error');
  }
  btn.disabled = false;
  btn.textContent = '➕ Create Task';
}

// ============================================================
// LEADERBOARD
// ============================================================
async function loadLeaderboard() {
  const container = document.getElementById('leaderboard-list');

  if (!container) return;

  container.innerHTML = `
    <div class="empty-state">
      <div class="empty-state-icon">⏳</div>
      <div class="empty-state-text">Loading...</div>
    </div>
  `;

  try {
    const res = await apiCall('/leaderboard');
    console.log('[LEADERBOARD] API response:', res);

    if (!res.ok) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">⚠️</div>
          <div class="empty-state-text">${res.data?.error || `Failed to load leaderboard (${res.status})`}</div>
        </div>
      `;
      return;
    }

    const leaderboard = Array.isArray(res.data?.leaderboard) ? res.data.leaderboard : [];

    if (leaderboard.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">🏆</div>
          <div class="empty-state-text">No leaderboard data yet</div>
        </div>
      `;
      return;
    }

    const RANK_EMOJI = { 1: '🥇', 2: '🥈', 3: '🥉' };

    container.innerHTML = leaderboard.map(entry => `
      <div class="lb-row ${entry.is_me ? 'is-me' : ''} ${entry.rank <= 3 ? `top-${entry.rank}` : ''}">
        <div class="lb-rank">${RANK_EMOJI[entry.rank] || entry.rank}</div>
        <div class="lb-avatar">${(entry.first_name || '?')[0].toUpperCase()}</div>
        <div class="lb-info">
          <div class="lb-name">${entry.first_name || 'Anonymous'}${entry.is_me ? ' (You)' : ''}</div>
          <div class="lb-coins">${entry.username ? '@' + entry.username : ''}</div>
        </div>
        <div class="lb-amount">${formatCoins(entry.coins ?? entry.mined_coins_total ?? 0)} OX</div>
      </div>
    `).join('');

    const rankEl = document.getElementById('my-rank');
    if (rankEl) {
      rankEl.textContent = res.data?.my_rank ? `Your rank: #${res.data.my_rank}` : 'Your rank: —';
    }
  } catch (error) {
    console.error('[LEADERBOARD] Error:', error);
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">❌</div>
        <div class="empty-state-text">Failed to load leaderboard</div>
      </div>
    `;
  }
}

// ============================================================
// WITHDRAWAL
// ============================================================
async function loadWithdrawalInfo() {
  const res = await apiCall('/withdrawals');
  if (!res.ok) return;

  state.withdrawal = {
    minimumCoins: res.data.minimum_coins || 500000,
    feePercent: Number(res.data.fee_percent ?? 5),
    coinValueBdt: Number(res.data.coin_value_bdt || 0.001),
  };
  const availEl = document.getElementById('withdraw-available');
  const minEl = document.getElementById('withdraw-min');
  if (availEl && state.balance) availEl.textContent = formatCoinsExact(state.balance.available_coins);
  if (minEl) minEl.textContent = formatCoinsExact(res.data.minimum_coins);
  const amountEl = document.getElementById('withdraw-amount');
  if (amountEl) amountEl.min = state.withdrawal.minimumCoins;
  const rateEl = document.getElementById('withdraw-rate');
  if (rateEl) rateEl.textContent = formatCoinsExact(Math.round(1 / state.withdrawal.coinValueBdt));
  updateWithdrawalPreview();
}

function formatBdt(amount) {
  return `৳${amount.toLocaleString('en-BD', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function updateWithdrawalPreview() {
  const amount = parseInt(document.getElementById('withdraw-amount')?.value || '0', 10);
  const gross = amount * state.withdrawal.coinValueBdt;
  const fee = gross * state.withdrawal.feePercent / 100;
  const fields = {
    'withdraw-gross': formatBdt(gross),
    'withdraw-fee': formatBdt(fee),
    'withdraw-net': formatBdt(Math.max(0, gross - fee)),
  };
  Object.entries(fields).forEach(([id, value]) => {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
  });
}

async function submitWithdrawal() {
  const amount = parseInt(document.getElementById('withdraw-amount')?.value || '0');
  const method = document.querySelector('.method-btn.selected')?.dataset.method || '';
  const destination = document.getElementById('withdraw-destination')?.value || '';

  if (!amount || amount < state.withdrawal.minimumCoins || !method || !destination) {
    if (amount && amount < state.withdrawal.minimumCoins) {
      showToast(`Minimum withdrawal is ${formatCoinsExact(state.withdrawal.minimumCoins)} coins`, 'error');
      return;
    }
    showToast('Fill all fields', 'error');
    return;
  }

  const res = await apiCall('/withdrawals', 'POST', { amount_coins: amount, method, destination });
  if (res.ok) {
    showToast('💸 Withdrawal requested!', 'success');
    document.getElementById('withdraw-amount').value = '';
    updateWithdrawalPreview();
    loadWithdrawalInfo();
  } else {
    showToast(res.data.error || 'Withdrawal failed', 'error');
  }
}

function selectMethod(btn) {
  document.querySelectorAll('.method-btn').forEach(b => b.classList.remove('selected'));
  btn.classList.add('selected');
}

// ============================================================
// UTILITIES
// ============================================================
function formatTime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

function showToast(msg, type = '') {
  const toast = document.getElementById('toast');
  if (!toast) return;
  toast.textContent = msg;
  toast.className = `toast ${type} show`;
  clearTimeout(toast._timeout);
  toast._timeout = setTimeout(() => {
    toast.classList.remove('show');
  }, 3000);
}

function hideLoader() {
  const loader = document.getElementById('loader');
  if (loader) {
    loader.classList.add('hidden');
    setTimeout(() => loader.remove(), 600);
  }
}

// ============================================================
// INIT
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
  initTelegramApp();

  // Check for cached token
  const cached = localStorage.getItem('auth_token');
  if (cached) state.token = cached;

  authenticate();

  // Nav clicks
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => showScreen(item.dataset.screen));
  });

  // Mining orb click = start if not mining
  document.getElementById('mining-orb')?.addEventListener('click', () => {
    if (state.miningStatus && !state.miningStatus.is_mining) startMining();
  });
});

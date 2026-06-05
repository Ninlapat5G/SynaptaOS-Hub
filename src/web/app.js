/* app.js — SynaptaHub Admin (React + Tailwind, ไม่มี build step)
   คอมไพล์ JSX ในเบราว์เซอร์ด้วย Babel standalone · ธีม Deep Glass เดียวกับฝั่งแอป */

const { useState, useEffect, useRef, useCallback } = React;

// ── token + ตัวช่วยเรียก API ───────────────────────────────────────────────
let TOKEN = localStorage.getItem('admin_token') || '';

async function api(path, opts = {}) {
  opts.headers = Object.assign({}, opts.headers || {});
  if (TOKEN) opts.headers['Authorization'] = 'Bearer ' + TOKEN;
  const res = await fetch(path, opts);
  if (res.status === 401) {
    window.dispatchEvent(new Event('syn-unauth'));
    throw new Error('unauthorized');
  }
  if (!res.ok) {
    const e = await res.json().catch(() => ({}));
    throw new Error(e.error || ('HTTP ' + res.status));
  }
  return res.json();
}

const thDate = (sec) => sec ? new Date(sec * 1000).toLocaleString('th-TH') : 'ไม่ทราบ';

// ── ไอคอน (inline SVG) ─────────────────────────────────────────────────────
const Icon = ({ path, className = 'w-5 h-5' }) => (
  <svg viewBox="0 0 24 24" fill="currentColor" className={className}><path d={path} /></svg>
);
const ICONS = {
  users: 'M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z',
  agent: 'M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z',
  system: 'M19.43 12.98c.04-.32.07-.64.07-.98s-.03-.66-.07-.98l2.11-1.65c.19-.15.24-.42.12-.64l-2-3.46c-.12-.22-.39-.3-.61-.22l-2.49 1c-.52-.4-1.08-.73-1.69-.98l-.38-2.65C14.46 2.18 14.25 2 14 2h-4c-.25 0-.46.18-.49.42l-.38 2.65c-.61.25-1.17.59-1.69.98l-2.49-1c-.23-.09-.49 0-.61.22l-2 3.46c-.13.22-.07.49.12.64l2.11 1.65c-.04.32-.07.65-.07.98s.03.66.07.98l-2.11 1.65c-.19.15-.24.42-.12.64l2 3.46c.12.22.39.3.61.22l2.49-1c.52.4 1.08.73 1.69.98l.38 2.65c.03.24.24.42.49.42h4c.25 0 .46-.18.49-.42l.38-2.65c.61-.25 1.17-.59 1.69-.98l2.49 1c.23.09.49 0 .61-.22l2-3.46c.12-.22.07-.49-.12-.64l-2.11-1.65zM12 15.5c-1.93 0-3.5-1.57-3.5-3.5s1.57-3.5 3.5-3.5 3.5 1.57 3.5 3.5-1.57 3.5-3.5 3.5z',
  settings: 'M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm-6 9c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1 1.71 0 3.1 1.39 3.1 3.1v2z',
  refresh: 'M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z',
  send: 'M2.01 21L23 12 2.01 3 2 10l15 2-15 2z',
  location: 'M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5a2.5 2.5 0 010-5 2.5 2.5 0 010 5z',
};

// ── ชิ้นส่วน UI ที่ใช้ซ้ำ ───────────────────────────────────────────────────
const Card = ({ className = '', children }) => (
  <div className={'glass rounded-xl2 ' + className}>{children}</div>
);
const Badge = ({ children, color = 'accent' }) => {
  const map = {
    accent: 'text-accent border-accent/40 bg-accent/10',
    accent2: 'text-accent2 border-accent2/40 bg-accent2/10',
    ok: 'text-ok border-ok/40 bg-ok/10',
    dim: 'text-inkDim border-inkXdim/40 bg-white/5',
  };
  return <span className={'text-[11px] font-mono px-2 py-0.5 rounded-full border ' + (map[color] || map.accent)}>{children}</span>;
};
const Spinner = ({ text = 'กำลังโหลด...', danger }) => (
  <div className={'flex items-center justify-center gap-2 py-10 text-sm ' + (danger ? 'text-danger' : 'text-inkDim')}>
    {!danger && <span className="w-4 h-4 border-2 border-accent/40 border-t-accent rounded-full animate-spin" />}
    {text}
  </div>
);

// ── หน้าเข้าสู่ระบบ ─────────────────────────────────────────────────────────
function Login({ onSuccess }) {
  const [val, setVal] = useState('');
  const [err, setErr] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr(false);
    TOKEN = val.trim();
    try {
      await api('/admin/api/users');
      localStorage.setItem('admin_token', TOKEN);
      onSuccess();
    } catch (_) {
      setErr(true); TOKEN = ''; localStorage.removeItem('admin_token');
    } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-bg0/80 backdrop-blur-sm p-5">
      <Card className="w-full max-w-md p-8 fade-in">
        <div className="flex flex-col items-center text-center gap-2 mb-6">
          <img src="/admin/static/logo.jpg" alt="SynaptaOS" className="w-16 h-16 rounded-2xl glow-accent object-cover" />
          <h2 className="text-xl font-semibold mt-2">เข้าสู่ระบบผู้ดูแล</h2>
          <p className="text-sm text-inkDim">ระบุกุญแจความปลอดภัย (ADMIN_TOKEN) ของคุณ</p>
        </div>
        <form onSubmit={submit} className="flex flex-col gap-4">
          <input type="password" autoFocus value={val} onChange={(e) => setVal(e.target.value)}
            placeholder="ป้อนกุญแจความปลอดภัย..."
            className="w-full bg-bg1/70 border border-line rounded-xl2 px-4 py-3 outline-none focus:border-accent transition" />
          {err && <div className="text-danger text-sm text-center">กุญแจไม่ถูกต้อง โปรดลองอีกครั้ง</div>}
          <button disabled={busy} type="submit"
            className="w-full py-3 rounded-xl2 font-semibold text-bg0 disabled:opacity-60 transition hover:brightness-110"
            style={{ background: 'linear-gradient(120deg,#00D4FF,#B44FFF)' }}>
            {busy ? 'กำลังตรวจสอบ...' : 'ยืนยันตัวตน'}
          </button>
        </form>
      </Card>
    </div>
  );
}

// ── overlay เมื่อ Hub ออฟไลน์ — บล็อกการใช้งานจนกว่าจะต่อกลับ (web admin ผูกกับ Hub) ──
function HubOffline() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-bg0/90 backdrop-blur-md p-5">
      <Card className="w-full max-w-sm p-8 text-center fade-in">
        <div className="flex justify-center mb-4">
          <span className="w-10 h-10 border-2 border-danger/40 border-t-danger rounded-full animate-spin" />
        </div>
        <h2 className="text-lg font-semibold mb-2">Hub ออฟไลน์</h2>
        <p className="text-sm text-inkDim leading-relaxed">
          ขาดการเชื่อมต่อกับ Hub — กำลังพยายามเชื่อมต่อใหม่ให้อัตโนมัติ<br />
          ตรวจสอบว่าเครื่อง Hub เปิดอยู่และอยู่ในเครือข่ายเดียวกัน
        </p>
      </Card>
    </div>
  );
}

// ── ส่วนหัว + แท็บ ──────────────────────────────────────────────────────────
const TABS = [
  { id: 'users', label: 'ผู้ใช้งาน', icon: ICONS.users },
  { id: 'location', label: 'ตำแหน่ง', icon: ICONS.location },
  { id: 'agent', label: 'เอเจนต์', icon: ICONS.agent },
  { id: 'system', label: 'ระบบหลังบ้าน', icon: ICONS.system },
  { id: 'settings', label: 'ความปลอดภัย', icon: ICONS.settings },
];

function Header({ tab, setTab, online, hasToken, onLogout }) {
  return (
    <header className="glass-soft sticky top-0 z-30 border-b border-line">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex flex-wrap items-center gap-x-4 gap-y-3">
        <div className="flex items-center gap-2.5">
          <img src="/admin/static/logo.jpg" alt="SynaptaOS" className="w-8 h-8 rounded-lg glow-accent shrink-0 object-cover" />
          <h1 className="text-lg font-semibold">SynaptaOS <span className="text-gradient font-bold">Hub</span></h1>
          <Badge color="accent2">ADMIN</Badge>
        </div>

        <nav className="order-3 w-full md:order-2 md:w-auto md:flex-1 flex items-center gap-1.5 overflow-x-auto md:justify-center">
          {TABS.map((t) => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={'shrink-0 flex items-center gap-2 px-3.5 py-2 rounded-xl2 text-sm font-medium transition '
                + (tab === t.id ? 'bg-accent/15 text-accent' : 'text-inkDim hover:text-ink hover:bg-white/5')}>
              <Icon path={t.icon} className="w-4 h-4" />
              <span className="whitespace-nowrap">{t.label}</span>
            </button>
          ))}
        </nav>

        <div className="order-2 md:order-3 ml-auto flex items-center gap-3">
          <span className={'w-2.5 h-2.5 rounded-full ' + (online ? 'bg-ok pulse-online' : 'bg-inkXdim')} />
          <span className="text-xs text-inkDim hidden sm:inline">{online ? 'Hub Online' : 'เชื่อมต่อใหม่...'}</span>
          {hasToken && (
            <button onClick={onLogout}
              className="text-xs px-3 py-1.5 rounded-lg border border-line text-inkDim hover:text-ink hover:border-lineStrong transition">
              ออกจากระบบ
            </button>
          )}
        </div>
      </div>
    </header>
  );
}

// ── ตัวแสดงข้อมูลแต่ละส่วนของผู้ใช้ (profile / kd / scenes / routines / phone) ──
function ProfileView({ d }) {
  const fields = [
    ['ชื่อผู้ใช้งาน (Display Name)', d.displayName],
    ['ชื่อผู้ช่วย (Assistant)', d.assistantName],
    ['เกี่ยวกับผู้ใช้ (Bio)', d.userBio],
    ['ความจำระยะยาวของบอท', d.userMemory],
    ['ลงทะเบียนเมื่อ', d.registered_at ? thDate(d.registered_at) : null],
  ];
  return (
    <div className="grid gap-3 fade-in">
      {fields.map(([label, val]) => (
        <div key={label} className="glass-soft rounded-xl2 p-4">
          <div className="text-[11px] uppercase tracking-wide text-accent mb-1">{label}</div>
          <div className="text-sm text-ink whitespace-pre-wrap break-words">{val || '— ไม่มีข้อมูล —'}</div>
        </div>
      ))}
      <div className="glass-soft rounded-xl2 p-4">
        <div className="text-[11px] uppercase tracking-wide text-accent2 mb-1">System Prompt ของบอท</div>
        <div className="text-[13px] font-mono text-inkDim whitespace-pre-wrap break-words">{d.systemPrompt || '— ไม่มีข้อมูล —'}</div>
      </div>
    </div>
  );
}

const DEV_ICON = { lamp: '💡', bulb: '💡', sparkle: '✨', gauge: '📊', fan: '🌀', ac: '❄️', tv: '📺' };
function KdView({ d }) {
  if (!Array.isArray(d) || d.length === 0) return <Spinner text="ไม่มีรายการอุปกรณ์" />;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 fade-in">
      {d.map((dev, i) => (
        <div key={i} className="glass-soft rounded-xl2 p-4 flex items-center gap-3 hover:border-accent/40 transition">
          <div className="w-11 h-11 rounded-xl2 bg-accent/10 flex items-center justify-center text-xl shrink-0">{DEV_ICON[dev.icon] || '🔌'}</div>
          <div className="min-w-0">
            <div className="font-medium truncate" title={dev.name}>{dev.name}</div>
            <div className="text-xs text-inkDim truncate">{dev.room || '—'}</div>
            <div className="mt-1"><Badge color="dim">{dev.type}</Badge></div>
          </div>
        </div>
      ))}
    </div>
  );
}

function ScenesView({ d }) {
  if (!Array.isArray(d) || d.length === 0) return <Spinner text="ไม่มีสภาพแวดล้อม (Scenes)" />;
  return (
    <div className="grid gap-3 fade-in">
      {d.map((sc, i) => (
        <div key={i} className="glass-soft rounded-xl2 p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="font-medium">✨ {sc.name}</div>
            <Badge color="accent2">{sc.id}</Badge>
          </div>
          <div className="text-[11px] uppercase tracking-wide text-accent mb-2">คำสั่งอุปกรณ์</div>
          <div className="flex flex-wrap gap-2">
            {Array.isArray(sc.actions) && sc.actions.length > 0
              ? sc.actions.map((a, j) => (
                <span key={j} className="text-xs bg-bg1/60 border border-line rounded-lg px-2.5 py-1">
                  <span className="text-inkDim">{a.deviceId}</span> <span className="text-accent font-mono">{a.value}</span>
                </span>))
              : <span className="text-xs text-inkXdim">(ไม่มีคำสั่ง)</span>}
          </div>
          {sc.prompt && <div className="text-xs mt-3"><span className="text-accent2 font-semibold">Prompt:</span> <span className="text-inkDim">{sc.prompt}</span></div>}
        </div>
      ))}
    </div>
  );
}

function RoutinesView({ d }) {
  if (!Array.isArray(d) || d.length === 0) return <Spinner text="ไม่มีกฎอัตโนมัติ (Routines)" />;
  const actLabel = (a) => a.type === 'prompt' ? `💬 รัน Prompt: "${a.prompt}"`
    : a.type === 'scene' ? `🎬 เรียกซีน: ${a.sceneId}` : '⚙️ ปรับค่าอุปกรณ์';
  return (
    <div className="grid gap-3 fade-in">
      {d.map((rt, i) => (
        <div key={i} className="glass-soft rounded-xl2 p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="font-medium">🤖 {rt.name}</div>
            {rt.enabled ? <Badge color="ok">เปิดใช้งาน</Badge> : <Badge color="dim">ปิดใช้งาน</Badge>}
          </div>
          <div className="text-[11px] uppercase tracking-wide text-accent mb-2">เมื่อตรงเงื่อนไข ({rt.logic || 'AND'})</div>
          <div className="flex flex-wrap gap-2 mb-3">
            {Array.isArray(rt.conditions) && rt.conditions.length > 0
              ? rt.conditions.map((c, j) => (
                <span key={j} className="text-xs bg-bg1/60 border border-line rounded-lg px-2.5 py-1">
                  <span className="text-inkDim">{c.source}</span> <span className="text-accent font-mono">{c.op} {c.value}</span>
                </span>))
              : <span className="text-xs text-inkXdim">(ไม่มีเงื่อนไข)</span>}
          </div>
          <div className="bg-white/[0.02] rounded-xl2 p-3">
            <div className="text-[11px] uppercase tracking-wide text-accent2 mb-2">ระบบจะทำงาน</div>
            {Array.isArray(rt.actions) && rt.actions.length > 0
              ? rt.actions.map((a, j) => <div key={j} className="text-[13px] mb-1">{actLabel(a)}</div>)
              : <span className="text-xs text-inkXdim">(ไม่มีผลลัพธ์)</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

function PhoneView({ d }) {
  const lvl = d && d.level !== undefined ? d.level : 0;
  return (
    <div className="fade-in flex flex-col sm:flex-row items-center gap-6 glass-soft rounded-xl2 p-6">
      <div className="battery-ring w-28 h-28 rounded-full flex items-center justify-center shrink-0" style={{ '--p': lvl }}>
        <div className="w-20 h-20 rounded-full bg-bg1 flex items-center justify-center text-xl font-mono font-semibold text-accent">{lvl}%</div>
      </div>
      <div className="text-center sm:text-left">
        <div className="text-lg font-medium">{(d && d.text) || `แบตเตอรี่ ${lvl}%`}</div>
        <div className="text-sm text-inkDim mt-1">{d && d.charging ? 'กำลังชาร์จไฟ ⚡' : 'ไม่ได้ชาร์จไฟ'}</div>
      </div>
    </div>
  );
}

const PART_LABELS = { profile: 'ข้อมูลส่วนตัว', kd: 'อุปกรณ์ (KD)', scenes: 'Scenes', routines: 'Routines', phone: 'มือถือ' };
const PART_KEYS = ['profile', 'kd', 'scenes', 'routines', 'phone'];

function PartView({ part, data }) {
  if (data === null || data === undefined) return <Spinner text="ไม่มีข้อมูลสำหรับส่วนนี้" />;
  if (part === 'profile') return <ProfileView d={data} />;
  if (part === 'kd') return <KdView d={data} />;
  if (part === 'scenes') return <ScenesView d={data} />;
  if (part === 'routines') return <RoutinesView d={data} />;
  if (part === 'phone') return <PhoneView d={data} />;
  return null;
}

// ── แท็บ 1: ผู้ใช้งาน ───────────────────────────────────────────────────────
function UsersTab({ users, reloadUsers, liveUpdate }) {
  const [sel, setSel] = useState(null);
  const [part, setPart] = useState('profile');
  const [data, setData] = useState(undefined);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState('');

  const deleteUser = async (uid) => {
    if (!confirm(`คุณแน่ใจหรือไม่ว่าต้องการลบผู้ใช้ ${uid}?\nข้อมูลทั้งหมด (Profile, อุปกรณ์, Scenes, Routines) จะถูกลบออกอย่างถาวร`)) {
      return;
    }
    try {
      await api(`/admin/api/users/${uid}`, { method: 'DELETE' });
      setSel(null);
      reloadUsers();
    } catch (e) {
      alert('ลบไม่สำเร็จ: ' + e.message);
    }
  };

  const loadPart = useCallback(async (uid, p) => {
    if (!uid) return;
    setLoading(true); setErr(''); setData(undefined);
    try {
      const d = await api(`/admin/api/users/${uid}/${p}`);
      setData(d);
    } catch (e) {
      if (e.message !== 'unauthorized') setErr(e.message);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { if (sel) loadPart(sel, part); }, [sel, part, loadPart]);

  // อัปเดตสด: ถ้า ws ส่งข้อมูลของ user/part ที่เปิดอยู่พอดี → รีเฟรชทันที
  useEffect(() => {
    if (liveUpdate && liveUpdate.user_id === sel && liveUpdate.kind === part) {
      setData(liveUpdate.data);
    }
  }, [liveUpdate, sel, part]);

  const ids = Object.keys(users);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4">
      {/* รายชื่อผู้ใช้ */}
      <Card className="p-4 h-fit">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">รายชื่อผู้ใช้ ({ids.length})</h2>
          <button onClick={reloadUsers} title="โหลดใหม่"
            className="w-8 h-8 flex items-center justify-center rounded-lg text-inkDim hover:text-accent hover:bg-white/5 transition">
            <Icon path={ICONS.refresh} className="w-4 h-4" />
          </button>
        </div>
        <div className="flex flex-col gap-2 max-h-[70vh] overflow-y-auto">
          {ids.length === 0 && <Spinner text="ไม่พบผู้ใช้ในระบบ" />}
          {ids.map((uid) => (
            <button key={uid} onClick={() => setSel(uid)}
              className={'text-left p-3 rounded-xl2 border transition '
                + (sel === uid ? 'border-accent/50 bg-accent/10' : 'border-line glass-soft hover:border-lineStrong')}>
              <div className="font-medium text-sm truncate font-mono">{uid}</div>
              <div className="text-xs text-inkDim truncate mt-0.5">{users[uid].app_name || 'แอปนิรนาม'} • {thDate(users[uid].last_seen)}</div>
            </button>
          ))}
        </div>
      </Card>

      {/* รายละเอียด */}
      {!sel ? (
        <Card className="p-10 flex flex-col items-center justify-center text-center text-inkDim min-h-[40vh]">
          <Icon path={ICONS.users} className="w-12 h-12 mb-3 text-inkXdim" />
          <p>เลือกผู้ใช้จากรายการเพื่อดูข้อมูลระบบ</p>
        </Card>
      ) : (
        <Card className="p-4 sm:p-5">
          <div className="mb-4 flex justify-between items-start gap-4">
            <div>
              <h3 className="font-semibold font-mono text-sm break-all">{sel}</h3>
              <p className="text-xs text-inkDim mt-0.5">แอป: {users[sel] && users[sel].app_name || '—'} • ล่าสุด: {thDate(users[sel] && users[sel].last_seen)}</p>
            </div>
            <button onClick={() => deleteUser(sel)}
              className="text-xs px-3 py-1.5 rounded-lg border border-red-500/40 text-red-400 hover:text-red-300 hover:bg-red-500/10 hover:border-red-500 transition">
              ลบผู้ใช้
            </button>
          </div>
          <div className="flex items-center gap-1.5 overflow-x-auto border-b border-line pb-3 mb-4">
            {PART_KEYS.map((p) => (
              <button key={p} onClick={() => setPart(p)}
                className={'shrink-0 px-3 py-1.5 rounded-lg text-sm font-medium transition '
                  + (part === p ? 'bg-accent/15 text-accent' : 'text-inkDim hover:text-ink hover:bg-white/5')}>
                {PART_LABELS[p]}
              </button>
            ))}
          </div>
          {loading ? <Spinner /> : err ? <Spinner text={'โหลดล้มเหลว: ' + err} danger /> : <PartView part={part} data={data} />}
        </Card>
      )}
    </div>
  );
}

// ── แท็บ 2: เอเจนต์ ─────────────────────────────────────────────────────────
// msgs/ctxUser ยกขึ้นไปไว้ที่ App → สลับแท็บแล้วบทสนทนาไม่หาย (อยู่จน refresh หน้า)
function AgentTab({ users, msgs, setMsgs, ctxUser, setCtxUser }) {
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const boxRef = useRef(null);

  useEffect(() => { if (boxRef.current) boxRef.current.scrollTop = boxRef.current.scrollHeight; }, [msgs, busy]);

  const send = async (e) => {
    e.preventDefault();
    const task = input.trim();
    if (!task || busy) return;
    setInput('');
    // ประวัติที่ส่งไปให้ agent จำบริบท (ก่อนเพิ่มข้อความใหม่) — เอาเฉพาะ user/agent
    const history = msgs.filter((m) => m.role === 'user' || m.role === 'agent').map((m) => ({ role: m.role, text: m.text }));
    setMsgs((m) => [...m, { role: 'user', text: task }]);
    setBusy(true);
    try {
      const r = await api('/admin/api/agent', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, user_id: ctxUser || null, history }),
      });
      setMsgs((m) => [...m, { role: 'agent', text: r.reply || '[ไม่มีการตอบกลับ]' }]);
    } catch (err) {
      if (err.message !== 'unauthorized') setMsgs((m) => [...m, { role: 'sys', text: 'เกิดข้อผิดพลาด: ' + err.message }]);
    } finally { setBusy(false); }
  };

  const bubble = (m, i) => {
    if (m.role === 'sys') return <div key={i} className="mx-auto text-center text-xs text-inkDim bg-white/5 rounded-xl2 px-4 py-2 max-w-lg">{m.text}</div>;
    const me = m.role === 'user';
    return (
      <div key={i} className={'max-w-[85%] sm:max-w-[75%] px-4 py-2.5 rounded-xl2 text-sm whitespace-pre-wrap break-words '
        + (me ? 'self-end text-bg0 font-medium' : 'self-start glass-soft')}
        style={me ? { background: 'linear-gradient(120deg,#00D4FF,#B44FFF)' } : {}}>
        {m.text}
      </div>
    );
  };

  return (
    <Card className="p-4 sm:p-5 flex flex-col h-[76vh]">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-line">
        <div className="flex items-center gap-2">
          <h2 className="font-semibold">สั่งการเอเจนต์ (Agent Shell)</h2>
          <button onClick={() => setMsgs([{ role: 'sys', text: 'เริ่มบทสนทนาใหม่แล้ว — พิมพ์คำสั่งให้เอเจนต์ได้เลย' }])}
            title="ล้างประวัติบทสนทนา"
            className="text-xs px-2.5 py-1 rounded-lg border border-line text-inkDim hover:text-danger hover:border-danger/40 transition">
            ล้างประวัติ
          </button>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-inkDim whitespace-nowrap">โฟกัสที่ผู้ใช้:</span>
          <select value={ctxUser} onChange={(e) => setCtxUser(e.target.value)}
            className="bg-bg1/70 border border-line rounded-lg px-2 py-1.5 outline-none focus:border-accent max-w-[60vw] sm:max-w-xs"
            title="เลือกคน = สั่งงาน/คุยในบริบทของคนนั้น · อัตโนมัติ = ให้ซินเลือกคนเองจากคำสั่ง">
            <option value="">— อัตโนมัติ (ซินเลือกคนเอง) —</option>
            {Object.keys(users).map((uid) => <option key={uid} value={uid}>{users[uid].app_name || 'แอป'} ({uid})</option>)}
          </select>
        </div>
      </div>

      <div ref={boxRef} className="flex-1 overflow-y-auto flex flex-col gap-3 py-4">
        {msgs.map(bubble)}
        {busy && (
          <div className="self-start glass-soft rounded-xl2 px-4 py-3 flex items-center gap-1.5 text-sm text-inkDim">
            <span className="think-dot w-2 h-2 rounded-full bg-accent" />
            <span className="think-dot w-2 h-2 rounded-full bg-accent" />
            <span className="think-dot w-2 h-2 rounded-full bg-accent" />
            <span className="ml-2">เอเจนต์กำลังคิด...</span>
          </div>
        )}
      </div>

      <form onSubmit={send} className="flex items-center gap-2 pt-3 border-t border-line">
        <input value={input} onChange={(e) => setInput(e.target.value)} disabled={busy}
          placeholder="พิมพ์สิ่งที่ต้องการให้ระบบทำ..."
          className="flex-1 bg-bg1/70 border border-line rounded-xl2 px-4 py-3 outline-none focus:border-accent transition disabled:opacity-60" />
        <button type="submit" disabled={busy}
          className="px-4 py-3 rounded-xl2 font-semibold text-bg0 disabled:opacity-60 transition hover:brightness-110 flex items-center gap-2"
          style={{ background: 'linear-gradient(120deg,#00D4FF,#B44FFF)' }}>
          <Icon path={ICONS.send} className="w-4 h-4" /><span className="hidden sm:inline">ส่ง</span>
        </button>
      </form>
    </Card>
  );
}

// ── แท็บ 3: ระบบหลังบ้าน ────────────────────────────────────────────────────
function SystemTab() {
  const [info, setInfo] = useState('');
  const [tools, setTools] = useState(null);
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    setErr(''); setInfo(''); setTools(null);
    try {
      const d = await api('/admin/api/system');
      setInfo(d.system_info || ''); setTools(d.tools || []);
    } catch (e) { if (e.message !== 'unauthorized') setErr(e.message); }
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <Card className="p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="font-semibold">ข้อมูลเครื่อง</h2>
          <button onClick={load} className="w-8 h-8 flex items-center justify-center rounded-lg text-inkDim hover:text-accent hover:bg-white/5 transition">
            <Icon path={ICONS.refresh} className="w-4 h-4" />
          </button>
        </div>
        {err ? <Spinner text={'โหลดล้มเหลว: ' + err} danger />
          : !info ? <Spinner />
            : <pre className="text-[13px] font-mono text-inkDim whitespace-pre-wrap break-words bg-bg1/50 rounded-xl2 p-4 max-h-[70vh] overflow-auto">{info}</pre>}
      </Card>

      <Card className="p-5">
        <h2 className="font-semibold mb-3">เครื่องมือที่เปิดใช้ (MCP Tools) {tools && <span className="text-inkDim font-normal">· {tools.length}</span>}</h2>
        {tools === null ? <Spinner /> : tools.length === 0 ? <Spinner text="ไม่พบเครื่องมือ" />
          : <div className="grid sm:grid-cols-2 gap-3 max-h-[70vh] overflow-y-auto">
            {tools.map((t, i) => (
              <div key={i} className="glass-soft rounded-xl2 p-3.5 hover:border-accent/40 transition">
                <div className="font-mono text-sm text-accent break-all">{t.name}</div>
                <div className="text-xs text-inkDim mt-1 line-clamp-3">{t.description || 'ไม่มีคำอธิบาย'}</div>
              </div>
            ))}
          </div>}
      </Card>
    </div>
  );
}

// ── แท็บ 4: ความปลอดภัย ─────────────────────────────────────────────────────
function SettingsTab({ onTokenSaved }) {
  const [adminSet, setAdminSet] = useState(false);
  const [oldTok, setOldTok] = useState('');
  const [newAdmin, setNewAdmin] = useState('');
  const [mcp, setMcp] = useState('');
  const [msg, setMsg] = useState(null); // {ok, text}
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setMsg(null);
    try {
      const d = await api('/admin/api/settings/passwords');
      setAdminSet(!!d.admin_token_set); setMcp(d.mcp_token || '');
    } catch (e) { if (e.message !== 'unauthorized') setMsg({ ok: false, text: e.message }); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const save = async (e) => {
    e.preventDefault();
    setBusy(true); setMsg(null);
    try {
      await api('/admin/api/settings/passwords', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_admin_token: oldTok, new_admin_token: newAdmin.trim(), new_mcp_token: mcp.trim() }),
      });
      TOKEN = newAdmin.trim();
      if (TOKEN) localStorage.setItem('admin_token', TOKEN); else localStorage.removeItem('admin_token');
      onTokenSaved && onTokenSaved();
      setMsg({ ok: true, text: '✓ บันทึกเรียบร้อยแล้ว' });
      setOldTok(''); setNewAdmin('');
      setTimeout(load, 800);
    } catch (err) {
      if (err.message !== 'unauthorized') {
        setMsg({ ok: false, text: err.message === 'incorrect old password' ? 'รหัสผ่านเดิมไม่ถูกต้อง' : 'บันทึกล้มเหลว: ' + err.message });
      }
    } finally { setBusy(false); }
  };

  const field = 'w-full bg-bg1/70 border border-line rounded-xl2 px-4 py-3 outline-none focus:border-accent transition';
  return (
    <div className="flex justify-center">
      <Card className="w-full max-w-lg p-6 sm:p-8">
        <h2 className="font-semibold text-center mb-6">ตั้งค่ากุญแจความปลอดภัย</h2>
        <form onSubmit={save} className="flex flex-col gap-4">
          <div>
            <label className="block text-sm text-inkDim mb-2">รหัสผ่านผู้ดูแลเดิม (ยืนยันตัวตน)</label>
            <input type="password" value={oldTok} onChange={(e) => setOldTok(e.target.value)} disabled={!adminSet}
              placeholder={adminSet ? 'ระบุรหัสเดิมเพื่อยืนยัน...' : 'ยังไม่เคยตั้งรหัส (เว้นว่างได้)'} className={field + (adminSet ? '' : ' opacity-50')} />
          </div>
          <div className="border-t border-line pt-4">
            <label className="block text-sm text-inkDim mb-2">รหัสผ่านผู้ดูแลใหม่ (ADMIN_TOKEN)</label>
            <input type="password" value={newAdmin} onChange={(e) => setNewAdmin(e.target.value)}
              placeholder="เว้นว่าง = เข้าได้โดยไม่ต้องใช้รหัส" className={field} />
          </div>
          <div>
            <label className="block text-sm text-inkDim mb-2">รหัสสำหรับแอปมือถือ (MCP_TOKEN)</label>
            <input type="text" value={mcp} onChange={(e) => setMcp(e.target.value)}
              placeholder="เว้นว่าง = ไม่เปิดใช้กุญแจ" className={field + ' font-mono'} />
          </div>
          {msg && <div className={'text-sm text-center ' + (msg.ok ? 'text-ok' : 'text-danger')}>{msg.text}</div>}
          <button type="submit" disabled={busy}
            className="w-full py-3 rounded-xl2 font-semibold text-bg0 disabled:opacity-60 transition hover:brightness-110"
            style={{ background: 'linear-gradient(120deg,#00D4FF,#B44FFF)' }}>
            {busy ? 'กำลังบันทึก...' : 'บันทึกการตั้งค่า'}
          </button>
        </form>
      </Card>
    </div>
  );
}

// ── แท็บ: ตำแหน่ง (Location) ─────────────────────────────────────────────────
// โชว์พิกัด lat/lng ของแต่ละ user (มาจาก telemetry ที่ background process ส่งขึ้นมา)
// + แผนที่ OpenStreetMap แบบ embed (ไม่ต้องใช้ API key — รันบน RPi ได้ตรง ๆ)
const osmEmbed = (lat, lng) => {
  const d = 0.008;
  const bbox = `${lng - d},${lat - d},${lng + d},${lat + d}`;
  return `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lng}`;
};
const gmapsLink = (lat, lng) => `https://www.google.com/maps?q=${lat},${lng}`;

function LocationCard({ uid, user, phone }) {
  const lat = phone && typeof phone.lat === 'number' ? phone.lat : null;
  const lng = phone && typeof phone.lng === 'number' ? phone.lng : null;
  const has = lat !== null && lng !== null;
  return (
    <Card className="p-4 fade-in">
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="min-w-0">
          <div className="font-medium truncate">{(user && user.app_name) || 'แอปนิรนาม'}</div>
          <div className="text-xs text-inkDim font-mono truncate">{uid}</div>
        </div>
        {phone && phone.moving
          ? <Badge color="accent">กำลังเคลื่อนที่</Badge>
          : <Badge color="dim">อยู่นิ่ง</Badge>}
      </div>

      {has ? (
        <>
          <div className="rounded-xl2 overflow-hidden border border-line mb-3">
            <iframe title={'map-' + uid} className="w-full h-52" loading="lazy"
              src={osmEmbed(lat, lng)} style={{ border: 0 }} />
          </div>
          <div className="grid grid-cols-2 gap-2 mb-3">
            <div className="glass-soft rounded-xl2 p-2.5">
              <div className="text-[10px] uppercase tracking-wide text-accent mb-0.5">Latitude</div>
              <div className="font-mono text-sm">{lat.toFixed(6)}</div>
            </div>
            <div className="glass-soft rounded-xl2 p-2.5">
              <div className="text-[10px] uppercase tracking-wide text-accent mb-0.5">Longitude</div>
              <div className="font-mono text-sm">{lng.toFixed(6)}</div>
            </div>
          </div>
          <div className="flex items-center justify-between text-xs text-inkDim">
            <span>🔋 {phone && phone.level !== undefined ? phone.level + '%' : '—'}{phone && phone.charging ? ' ⚡' : ''}</span>
            <a href={gmapsLink(lat, lng)} target="_blank" rel="noreferrer"
              className="text-accent hover:underline">เปิดใน Google Maps →</a>
          </div>
        </>
      ) : (
        <div className="text-sm text-inkXdim py-8 text-center">ยังไม่มีพิกัด (ผู้ใช้อาจปิดตำแหน่ง หรือยังไม่ส่ง telemetry)</div>
      )}
    </Card>
  );
}

function LocationTab({ users, liveUpdate }) {
  const [locs, setLocs] = useState({}); // uid → phone data
  const [loading, setLoading] = useState(true);
  const ids = Object.keys(users);

  const loadAll = useCallback(async () => {
    setLoading(true);
    const entries = await Promise.all(Object.keys(users).map(async (uid) => {
      try { return [uid, await api(`/admin/api/users/${uid}/phone`)]; }
      catch (_) { return [uid, null]; }
    }));
    setLocs(Object.fromEntries(entries));
    setLoading(false);
  }, [users]);

  useEffect(() => { loadAll(); }, [loadAll]);

  // อัปเดตสด: telemetry ของใครเข้ามา → ขยับหมุดคนนั้นทันที
  useEffect(() => {
    if (liveUpdate && liveUpdate.kind === 'phone') {
      setLocs((prev) => ({ ...prev, [liveUpdate.user_id]: liveUpdate.data }));
    }
  }, [liveUpdate]);

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold">ตำแหน่งผู้ใช้ ({ids.length})</h2>
        <button onClick={loadAll} title="โหลดใหม่"
          className="w-8 h-8 flex items-center justify-center rounded-lg text-inkDim hover:text-accent hover:bg-white/5 transition">
          <Icon path={ICONS.refresh} className="w-4 h-4" />
        </button>
      </div>
      {loading ? <Spinner /> : ids.length === 0 ? <Spinner text="ไม่พบผู้ใช้ในระบบ" />
        : <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {ids.map((uid) => <LocationCard key={uid} uid={uid} user={users[uid]} phone={locs[uid]} />)}
        </div>}
    </div>
  );
}

// ── แอปหลัก ─────────────────────────────────────────────────────────────────
function App() {
  const [ready, setReady] = useState(false);     // ตรวจสิทธิ์เสร็จแล้ว
  const [needLogin, setNeedLogin] = useState(false);
  const [tab, setTab] = useState('users');
  const [users, setUsers] = useState({});
  const [online, setOnline] = useState(false);
  const [hubDown, setHubDown] = useState(false); // ออฟไลน์ค้างเกิน 4 วิ → บล็อกหน้าจอ
  const [liveUpdate, setLiveUpdate] = useState(null);
  // บทสนทนาแท็บเอเจนต์ — เก็บในหน่วยความจำเท่านั้น (คงอยู่ข้ามการสลับแท็บ แต่ reload หน้า = เริ่มใหม่)
  const [agentMsgs, setAgentMsgs] = useState([{ role: 'sys', text: 'ระบบพร้อมแล้ว พิมพ์คำสั่งให้เอเจนต์ทำงานได้เลย เช่น "เปิดเพลง lofi" หรือ "ดู disk ที่เหลือ"' }]);
  const [agentCtxUser, setAgentCtxUser] = useState('');
  const wsRef = useRef(null);

  const reloadUsers = useCallback(async () => {
    try { setUsers(await api('/admin/api/users')); }
    catch (e) { /* 401 จะเด้ง event เอง */ }
  }, []);

  const connectWS = useCallback(() => {
    if (wsRef.current) { try { wsRef.current.close(); } catch (_) {} }
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const q = TOKEN ? '?token=' + encodeURIComponent(TOKEN) : '';
    const ws = new WebSocket(`${proto}//${location.host}/admin/ws${q}`);
    wsRef.current = ws;
    ws.onopen = () => setOnline(true);
    ws.onmessage = (ev) => {
      try {
        const m = JSON.parse(ev.data);
        if (m.type === 'update') {
          if (m.kind === 'delete') {
            reloadUsers();
            return;
          }
          setUsers((prev) => {
            if (!prev[m.user_id]) { reloadUsers(); return prev; }
            return { ...prev, [m.user_id]: { ...prev[m.user_id], last_seen: Math.floor(Date.now() / 1000) } };
          });
          setLiveUpdate({ user_id: m.user_id, kind: m.kind, data: m.data, ts: Date.now() });
        }
      } catch (_) {}
    };
    ws.onclose = () => { setOnline(false); setTimeout(() => { if (!needLogin) connectWS(); }, 3000); };
    ws.onerror = () => {};
  }, [reloadUsers, needLogin]);

  const boot = useCallback(async () => {
    try {
      setUsers(await api('/admin/api/users'));
      setNeedLogin(false); setReady(true); connectWS();
    } catch (e) {
      if (e.message === 'unauthorized' || TOKEN) setNeedLogin(true);
      else { setNeedLogin(true); }
      setReady(true);
    }
  }, [connectWS]);

  useEffect(() => { boot(); }, [boot]);

  // ดัก 401 จากที่ใด ๆ → เด้งหน้า login
  useEffect(() => {
    const h = () => setNeedLogin(true);
    window.addEventListener('syn-unauth', h);
    return () => window.removeEventListener('syn-unauth', h);
  }, []);

  // Hub ออฟไลน์ค้าง (ws ต่อไม่ได้) เกิน 4 วิ → ขึ้น overlay บล็อก (กันแฟลชตอนหลุดแวบเดียว)
  useEffect(() => {
    if (online) { setHubDown(false); return; }
    const t = setTimeout(() => setHubDown(true), 4000);
    return () => clearTimeout(t);
  }, [online]);

  const onLoginSuccess = () => { setNeedLogin(false); reloadUsers(); connectWS(); };
  const logout = () => {
    TOKEN = ''; localStorage.removeItem('admin_token');
    if (wsRef.current) { try { wsRef.current.close(); } catch (_) {} }
    setOnline(false); setNeedLogin(true);
  };

  if (!ready) return <div className="min-h-screen flex items-center justify-center"><Spinner /></div>;
  if (needLogin) return <Login onSuccess={onLoginSuccess} />;

  return (
    <div className="min-h-screen">
      <Header tab={tab} setTab={setTab} online={online} hasToken={!!TOKEN} onLogout={logout} />
      {/* คงทุกแท็บไว้ (ซ่อน/โชว์ด้วย display) — สลับแท็บแล้วข้อมูลแต่ละหน้าไม่หาย ไม่ต้องโหลดใหม่ */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-5">
        <div style={{ display: tab === 'users' ? '' : 'none' }}>
          <UsersTab users={users} reloadUsers={reloadUsers} liveUpdate={liveUpdate} />
        </div>
        <div style={{ display: tab === 'location' ? '' : 'none' }}>
          <LocationTab users={users} liveUpdate={liveUpdate} />
        </div>
        <div style={{ display: tab === 'agent' ? '' : 'none' }}>
          <AgentTab users={users} msgs={agentMsgs} setMsgs={setAgentMsgs} ctxUser={agentCtxUser} setCtxUser={setAgentCtxUser} />
        </div>
        <div style={{ display: tab === 'system' ? '' : 'none' }}>
          <SystemTab />
        </div>
        <div style={{ display: tab === 'settings' ? '' : 'none' }}>
          <SettingsTab onTokenSaved={reloadUsers} />
        </div>
      </main>
      {hubDown && <HubOffline />}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);

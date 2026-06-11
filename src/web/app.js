/* app.js — SynaptaHub Admin (React + Tailwind, ไม่มี build step)
   คอมไพล์ JSX ในเบราว์เซอร์ด้วย Babel standalone · ธีม Deep Glass เดียวกับฝั่งแอป */

const { useState, useEffect, useRef, useCallback } = React;

const MotionObj = window.Motion || window.FramerMotion || window.framerMotion;
const motion = MotionObj ? MotionObj.motion : {
  div: 'div', button: 'button', span: 'span', p: 'p', ul: 'ul', li: 'li',
  h2: 'h2', h3: 'h3', form: 'form', textarea: 'textarea', input: 'input'
};
const AnimatePresence = MotionObj ? MotionObj.AnimatePresence : React.Fragment;


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
  devices: 'M4 6H2v14c0 1.1.9 2 2 2h14v-2H4V6zm16-4H8c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 9h-8V5h8v6z',
  bolt: 'M11 21h-1l1-7H7.5c-.58 0-.57-.32-.38-.66.19-.34.05-.08.07-.12C8.48 10.94 10.42 7.54 13 3h1l-1 7h3.5c.49 0 .56.33.47.51l-.07.15C12.96 17.55 11 21 11 21z',
  clock: 'M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z',
  pulse: 'M3 13h2.79l2.46-7.39c.18-.55.96-.52 1.1.04l3.1 12.42 2.18-5.45c.15-.38.52-.62.93-.62H21v2h-4.76l-3.31 8.27c-.21.53-.98.49-1.12-.06L8.74 10.3l-1.29 3.86c-.14.41-.52.69-.95.69H3v-1.85z',
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
  { id: 'devices', label: 'อุปกรณ์ IoT', icon: ICONS.devices },
  { id: 'rules', label: 'กฎอัตโนมัติ', icon: ICONS.bolt },
  { id: 'jobs', label: 'งานตั้งเวลา', icon: ICONS.clock },
  { id: 'events', label: 'เหตุการณ์', icon: ICONS.pulse },
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

function DeviceCard({ dev, onControl, disabled }) {
  const isOnline = dev.state !== null && dev.state !== undefined;
  let displayValue = '—';
  let isOn = false;

  if (isOnline) {
    if (dev.type === 'digital') {
      const stateLower = String(dev.state).toLowerCase();
      isOn = stateLower === 'true' || stateLower === 'on' || stateLower === '1';
      displayValue = isOn ? 'เปิด' : 'ปิด';
    } else if (dev.type === 'analog') {
      const valInt = parseInt(dev.state, 10);
      isOn = valInt > 0;
      displayValue = `${valInt}/255`;
    } else if (dev.type === 'sensor') {
      displayValue = `${dev.state} ${dev.unit || ''}`.trim();
    }
  }

  const handleToggle = () => {
    if (disabled || dev.type === 'sensor') return;
    const nextVal = isOn ? 'false' : 'true';
    onControl(dev.topic, nextVal);
  };

  const handleSliderChange = (e) => {
    if (disabled) return;
    const nextVal = e.target.value;
    onControl(dev.topic, nextVal);
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      whileHover={{ y: -4 }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className={`glass-soft rounded-xl2 p-4 flex flex-col justify-between border transition-colors duration-300 ${
        isOn ? 'border-accent/40 bg-accent/5 shadow-[0_0_12px_rgba(0,212,255,0.06)]' : 'border-line hover:border-lineStrong'
      }`}
    >
      <div className="flex items-start gap-3 w-full">
        <div className={`w-11 h-11 rounded-xl2 flex items-center justify-center text-xl shrink-0 transition ${
          isOn ? 'bg-accent/20 text-accent scale-105' : 'bg-white/5 text-inkDim'
        }`}>
          {DEV_ICON[dev.icon] || '🔌'}
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-semibold text-sm truncate text-ink" title={dev.name}>{dev.name}</div>
          <div className="text-xs text-inkDim truncate mt-0.5">{dev.room || '—'}</div>
          {dev.userName && (
            <div className="text-[10px] text-inkXdim font-mono truncate mt-0.5">ผู้ใช้: {dev.userName}</div>
          )}
          <div className="text-[10px] text-inkXdim font-mono truncate">{dev.topic}</div>
        </div>
        <div className="text-right shrink-0">
          <span className={`text-xs font-mono font-bold px-2 py-0.5 rounded-full ${
            dev.type === 'sensor' 
              ? 'text-accent2 bg-accent2/10' 
              : isOn 
                ? 'text-ok bg-ok/10' 
                : 'text-inkDim bg-white/5'
          }`}>
            {displayValue}
          </span>
        </div>
      </div>

      {dev.type !== 'sensor' && (
        <div className="mt-4 pt-3 border-t border-line/40 flex items-center justify-between gap-4">
          {dev.type === 'digital' ? (
            <>
              <span className="text-[11px] text-inkDim">สั่งการ</span>
              <button 
                onClick={handleToggle}
                disabled={disabled}
                className={`text-xs px-3 py-1.5 rounded-lg font-medium transition ${
                  isOn 
                    ? 'bg-ok/25 text-ok hover:bg-ok/35 border border-ok/30' 
                    : 'bg-white/5 text-inkDim hover:bg-white/10 border border-line'
                }`}
              >
                {isOn ? 'ปิด (OFF)' : 'เปิด (ON)'}
              </button>
            </>
          ) : (
            <div className="w-full flex flex-col gap-1.5">
              <div className="flex justify-between text-[11px] text-inkDim">
                <span>ปรับความแรง/แสง</span>
                <span>{parseInt(dev.state || 0, 10)}</span>
              </div>
              <input 
                type="range" 
                min="0" 
                max="255" 
                value={parseInt(dev.state || 0, 10)} 
                onChange={handleSliderChange}
                disabled={disabled}
                className="w-full accent-accent bg-bg0 h-1.5 rounded-lg appearance-none cursor-pointer"
              />
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
}

function KdView({ d, onControl }) {
  if (!Array.isArray(d) || d.length === 0) return <Spinner text="ไม่มีรายการอุปกรณ์" />;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 fade-in">
      {d.map((dev, i) => (
        <DeviceCard key={i} dev={dev} onControl={onControl} />
      ))}
    </div>
  );
}

function DevicesTab() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [search, setSearch] = useState('');
  const [selectedUser, setSelectedUser] = useState('all');
  const [selectedRoom, setSelectedRoom] = useState('all');
  const [busyTopic, setBusyTopic] = useState(null);

  const fetchDevices = useCallback(async (showLoading = false) => {
    if (showLoading) setLoading(true);
    try {
      const list = await api('/admin/api/devices');
      setDevices(list);
      setErr('');
    } catch (e) {
      if (e.message !== 'unauthorized') setErr(e.message);
    } finally {
      if (showLoading) setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDevices(true);
    const interval = setInterval(() => {
      fetchDevices(false);
    }, 6000); // websocket คอยดันให้สดเสมออยู่แล้ว ปรับ polling เป็น 6 วินาทีเพื่อความเซฟ
    return () => clearInterval(interval);
  }, [fetchDevices]);

  useEffect(() => {
    const handleDeviceUpdate = (e) => {
      const { topic, state } = e.detail;
      setDevices((prev) => 
        prev.map(d => d.topic === topic ? { ...d, state: state } : d)
      );
    };
    window.addEventListener('syn-device-update', handleDeviceUpdate);
    return () => window.removeEventListener('syn-device-update', handleDeviceUpdate);
  }, []);

  const handleControl = async (topic, value) => {
    // อัปเดต UI ทันทีในเครื่องแบบ Optimistic (ความรู้สึกตอบสนองทันที 0ms)
    setDevices((prev) => 
      prev.map(d => d.topic === topic ? { ...d, state: value } : d)
    );
    setBusyTopic(topic);
    try {
      await api('/admin/api/devices/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, value })
      });
    } catch (e) {
      alert('ควบคุมอุปกรณ์ล้มเหลว: ' + e.message);
      fetchDevices(false); // โหลดใหม่เมื่อเกิดข้อผิดพลาดจริง
    } finally {
      setBusyTopic(null);
    }
  };

  const usersList = ['all', ...new Set(devices.map(d => d.uid))];
  const userNamesMap = devices.reduce((acc, d) => {
    acc[d.uid] = d.userName;
    return acc;
  }, {});

  const roomsList = ['all', ...new Set(devices.map(d => d.room))];

  const filtered = devices.filter((d) => {
    const matchesUser = selectedUser === 'all' || d.uid === selectedUser;
    const matchesRoom = selectedRoom === 'all' || d.room === selectedRoom;
    const matchesSearch = search.trim() === '' || 
      d.name.toLowerCase().includes(search.toLowerCase()) || 
      d.topic.toLowerCase().includes(search.toLowerCase()) ||
      d.room.toLowerCase().includes(search.toLowerCase());
    return matchesUser && matchesRoom && matchesSearch;
  });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-gradient">ระบบควบคุมอุปกรณ์ในบ้าน</h2>
          <p className="text-xs text-inkDim mt-0.5">รวมอุปกรณ์ทั้งหมดที่เชื่อมต่อกับระบบเพื่อการควบคุมแบบเรียลไทม์</p>
        </div>
        <button onClick={() => fetchDevices(true)} title="โหลดใหม่"
          className="w-10 h-10 flex items-center justify-center rounded-xl2 text-inkDim hover:text-accent bg-white/5 border border-line hover:border-lineStrong transition">
          <Icon path={ICONS.refresh} className="w-5 h-5" />
        </button>
      </div>

      <Card className="p-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label className="block text-[11px] uppercase tracking-wide text-accent font-semibold mb-1.5">ค้นหาอุปกรณ์</label>
          <input 
            type="text" 
            placeholder="ค้นหาชื่อ, topic หรือห้อง..." 
            value={search} 
            onChange={(e) => setSearch(e.target.value)}
            className="w-full text-xs bg-bg1/70 border border-line rounded-xl px-3 py-2 outline-none focus:border-accent transition text-ink"
          />
        </div>
        <div>
          <label className="block text-[11px] uppercase tracking-wide text-accent font-semibold mb-1.5">กรองตามผู้ใช้งาน</label>
          <select 
            value={selectedUser} 
            onChange={(e) => setSelectedUser(e.target.value)}
            className="w-full text-xs bg-bg1/70 border border-line rounded-xl px-3 py-2 outline-none focus:border-accent transition text-ink"
          >
            <option value="all">ทั้งหมด</option>
            {usersList.filter(u => u !== 'all').map(uid => (
              <option key={uid} value={uid}>{userNamesMap[uid] || uid}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-[11px] uppercase tracking-wide text-accent font-semibold mb-1.5">กรองตามห้อง</label>
          <select 
            value={selectedRoom} 
            onChange={(e) => setSelectedRoom(e.target.value)}
            className="w-full text-xs bg-bg1/70 border border-line rounded-xl px-3 py-2 outline-none focus:border-accent transition text-ink"
          >
            <option value="all">ทุกห้อง</option>
            {roomsList.filter(r => r !== 'all').map(r => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>
      </Card>

      {loading ? (
        <Spinner />
      ) : err ? (
        <Spinner text={'โหลดล้มเหลว: ' + err} danger />
      ) : filtered.length === 0 ? (
        <Card className="p-10 flex flex-col items-center justify-center text-center text-inkDim min-h-[30vh]">
          <span className="text-3xl mb-2">🔌</span>
          <p>ไม่พบอุปกรณ์ที่ตรงกับตัวกรอง</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 fade-in">
          {filtered.map((dev, i) => (
            <DeviceCard 
              key={i} 
              dev={dev} 
              onControl={handleControl} 
              disabled={busyTopic === dev.topic} 
            />
          ))}
        </div>
      )}
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

function PartView({ part, data, onDeviceControl }) {
  if (data === null || data === undefined) return <Spinner text="ไม่มีข้อมูลสำหรับส่วนนี้" />;
  if (part === 'profile') return <ProfileView d={data} />;
  if (part === 'kd') return <KdView d={data} onControl={onDeviceControl} />;
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

  const handleDeviceControl = async (topic, value) => {
    // Optimistic update
    if (part === 'kd' && Array.isArray(data)) {
      setData((prev) => 
        prev.map(d => d.topic === topic ? { ...d, state: value } : d)
      );
    }
    try {
      await api('/admin/api/devices/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic, value })
      });
    } catch (e) {
      alert('ควบคุมอุปกรณ์ล้มเหลว: ' + e.message);
      loadPart(sel, part);
    }
  };

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

  useEffect(() => {
    const handleDeviceUpdate = (e) => {
      const { topic, state } = e.detail;
      if (part === 'kd' && Array.isArray(data)) {
        setData((prev) => 
          prev.map(d => d.topic === topic ? { ...d, state: state } : d)
        );
      }
    };
    window.addEventListener('syn-device-update', handleDeviceUpdate);
    return () => window.removeEventListener('syn-device-update', handleDeviceUpdate);
  }, [part, data]);

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
              className="shrink-0 whitespace-nowrap text-xs px-3 py-1.5 rounded-lg border border-red-500/40 text-red-400 hover:text-red-300 hover:bg-red-500/10 hover:border-red-500 transition">
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
          {loading ? <Spinner /> : err ? <Spinner text={'โหลดล้มเหลว: ' + err} danger /> : <PartView part={part} data={data} onDeviceControl={handleDeviceControl} />}
        </Card>
      )}
    </div>
  );
}

// A component to display the tools call flow
function AgentStepsFlow({ steps }) {
  const MotionObj = window.Motion || window.FramerMotion || window.framerMotion;
  const MotionDiv = MotionObj && MotionObj.motion ? MotionObj.motion.div : 'div';
  const AnimatePresence = MotionObj ? MotionObj.AnimatePresence : React.Fragment;

  if (steps.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center p-6 text-inkDim text-xs h-full gap-2">
        <div className="text-xl">⚡</div>
        <p>สถานะการทำงานของ Agent (Tool Flow) จะแสดงขึ้นที่นี่ทีละขั้นตอนค่ะ</p>
      </div>
    );
  }

  const getArgsString = (args) => {
    if (!args) return '';
    if (typeof args === 'string') return args;
    try { return JSON.stringify(args, null, 2); }
    catch (_) { return String(args); }
  };

  const getResultString = (res) => {
    if (!res) return '';
    const s = String(res);
    if (s.length > 250) return s.slice(0, 247) + '...';
    return s;
  };

  return (
    <div className="flex flex-col gap-3 h-full overflow-y-auto pr-1">
      <div className="text-[11px] uppercase tracking-wide text-accent font-semibold mb-1 flex items-center justify-between">
        <span>กระบวนการทำงานเบื้องหลัง</span>
        {steps.some(s => s.status === 'running') && (
          <span className="w-2 h-2 rounded-full bg-accent animate-pulse"></span>
        )}
      </div>
      <AnimatePresence>
        {steps.map((s) => (
          <MotionDiv
            key={s.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className={`p-3 rounded-xl2 border text-xs flex flex-col gap-2 transition ${
              s.status === 'running'
                ? 'border-accent/40 bg-accent/5 shadow-[0_0_12px_rgba(0,212,255,0.12)]'
                : 'border-line bg-bg1/40'
            }`}
          >
            <div className="flex items-center gap-2 font-medium">
              {s.status === 'running' ? (
                <span className="flex h-2.5 w-2.5 relative shrink-0">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-accent"></span>
                </span>
              ) : (
                <span className="text-ok shrink-0">✓</span>
              )}
              <span className="truncate text-ink">{s.label}</span>
            </div>

            {s.args && (
              <div className="bg-bg0/80 rounded-lg p-2 font-mono text-[10px] text-inkDim overflow-x-auto whitespace-pre-wrap max-h-24">
                <span className="text-accent2">Input:</span> {getArgsString(s.args)}
              </div>
            )}

            {s.result && (
              <div className="bg-bg0/40 rounded-lg p-2 font-mono text-[10px] text-inkXdim overflow-x-auto whitespace-pre-wrap max-h-24 border border-line/40">
                <span className="text-ok">Output:</span> {getResultString(s.result)}
              </div>
            )}
          </MotionDiv>
        ))}
      </AnimatePresence>
    </div>
  );
}

// ── แท็บ 2: เอเจนต์ ─────────────────────────────────────────────────────────
// msgs/ctxUser ยกขึ้นไปไว้ที่ App → สลับแท็บแล้วบทสนทนาไม่หาย (อยู่จน refresh หน้า)
function AgentTab({ users, msgs, setMsgs, ctxUser, setCtxUser }) {
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [steps, setSteps] = useState([]);
  const boxRef = useRef(null);
  const wsRef = useRef(null);

  useEffect(() => {
    if (boxRef.current) boxRef.current.scrollTop = boxRef.current.scrollHeight;
  }, [msgs, busy]);

  // เคลียร์ WS เมื่อปิดหน้านี้
  useEffect(() => {
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const send = (e) => {
    e.preventDefault();
    const task = input.trim();
    if (!task || busy) return;
    setInput('');
    setBusy(true);
    setSteps([{ id: 'init', name: 'Plan', label: '🧠 กำลังวิเคราะห์และวางแผนงาน...', status: 'running' }]);

    const history = msgs
      .filter((m) => m.role === 'user' || m.role === 'agent')
      .map((m) => ({ role: m.role, text: m.text }));

    setMsgs((m) => [...m, { role: 'user', text: task }]);

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = localStorage.getItem('admin_token') || TOKEN;
    const q = token ? '?token=' + encodeURIComponent(token) : '';
    const ws = new WebSocket(`${proto}//${location.host}/admin/ws/agent${q}`);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ task, user_id: ctxUser || null, history }));
    };

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.type === 'tool_start') {
          setSteps((prev) => {
            const next = prev.map(s => s.id === 'init' ? { ...s, status: 'success', label: '🧠 วางแผนงานสำเร็จ' } : s);
            return [...next, {
              id: 'tool-' + Date.now() + '-' + Math.random(),
              name: data.name,
              label: `🔧 เรียกใช้: ${data.name}`,
              args: data.args,
              status: 'running'
            }];
          });
        }
        else if (data.type === 'tool_end') {
          setSteps((prev) => prev.map((s) => 
            s.name === data.name && s.status === 'running'
              ? { ...s, status: 'success', label: `✓ ทำงาน ${data.name} สำเร็จ`, result: data.result }
              : s
          ));
        }
        else if (data.type === 'reply_start') {
          setSteps((prev) => {
            const next = prev.map(s => s.status === 'running' ? { ...s, status: 'success' } : s);
            return [...next, {
              id: 'reply-init',
              name: 'Reply',
              label: '✍️ กำลังเรียบเรียงคำตอบสุดท้าย...',
              status: 'running'
            }];
          });
          setMsgs((m) => [...m, { role: 'agent', text: '', streaming: true }]);
        }
        else if (data.type === 'reply_chunk') {
          setMsgs((prev) => {
            const next = [...prev];
            if (next.length > 0 && next[next.length - 1].role === 'agent') {
              next[next.length - 1].text += data.text;
            }
            return next;
          });
        }
        else if (data.type === 'reply_end') {
          setSteps((prev) => prev.map((s) => s.id === 'reply-init' ? { ...s, status: 'success', label: '✓ ตอบกลับสำเร็จ' } : s));
          setMsgs((prev) => {
            const next = [...prev];
            if (next.length > 0 && next[next.length - 1].role === 'agent') {
              next[next.length - 1].text = data.reply;
              next[next.length - 1].streaming = false;
            }
            return next;
          });
          setBusy(false);
          ws.close();
        }
        else if (data.type === 'error') {
          setMsgs((m) => [...m, { role: 'sys', text: 'เกิดข้อผิดพลาด: ' + data.error }]);
          setBusy(false);
          ws.close();
        }
      } catch (err) {
        console.error(err);
      }
    };

    ws.onerror = () => {
      setMsgs((m) => [...m, { role: 'sys', text: 'การเชื่อมต่อ WebSocket สำหรับ Agent ขัดข้อง' }]);
      setBusy(false);
    };

    ws.onclose = () => {
      setBusy(false);
    };
  };

  const bubble = (m, i) => {
    if (m.role === 'sys') {
      return (
        <motion.div 
          key={i} 
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          className="mx-auto text-center text-xs text-inkDim bg-white/5 rounded-xl2 px-4 py-2 max-w-lg"
        >
          {m.text}
        </motion.div>
      );
    }
    const me = m.role === 'user';
    return (
      <motion.div 
        key={i} 
        initial={{ opacity: 0, scale: 0.96, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.22, ease: 'easeOut' }}
        className={'max-w-[85%] sm:max-w-[75%] px-4 py-2.5 rounded-xl2 text-sm whitespace-pre-wrap break-words '
          + (me ? 'self-end text-bg0 font-medium' : 'self-start glass-soft')}
        style={me ? { background: 'linear-gradient(120deg,#00D4FF,#B44FFF)' } : {}}
      >
        {m.text}
      </motion.div>
    );
  };

  return (
    <div className="flex flex-col lg:grid lg:grid-cols-[1fr_340px] gap-4 lg:h-[76vh]">
      {/* ฝั่งแชทบับเบิ้ล */}
      <Card className="p-4 sm:p-5 flex flex-col h-[72vh] lg:h-full border border-line">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-line">
          <div className="flex items-center gap-2">
            <img src="/admin/static/syn_icon_2.jpg" alt="ซิน" className="w-8 h-8 rounded-full object-cover glow-accent shrink-0" />
            <h2 className="font-semibold text-sm">สั่งการเอเจนต์ (Agent Shell)</h2>
            <button onClick={() => { setMsgs([{ role: 'sys', text: 'เริ่มบทสนทนาใหม่แล้ว — พิมพ์คำสั่งให้เอเจนต์ได้เลย' }]); setSteps([]); }}
              title="ล้างประวัติบทสนทนา"
              className="text-xs px-2.5 py-1 rounded-lg border border-line text-inkDim hover:text-danger hover:border-danger/40 transition">
              ล้างแชท
            </button>
          </div>
          <div className="flex items-center gap-2 text-xs">
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
          {!msgs.some((m) => m.role === 'user' || m.role === 'agent') ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center gap-3 px-6">
              <img src="/admin/static/syn_icon_2.jpg" alt="ซิน" className="w-24 h-24 rounded-full object-cover glow-accent" />
              <div className="text-base font-semibold">สั่งการระบบกลาง SynaptaOS</div>
              <p className="text-xs text-inkDim max-w-sm">พิมพ์คำสั่งภาษาคนเพื่อให้เอเจนต์ทำงานบนเครื่องนี้ได้เลยค่ะ เช่น “เปิดโปรแกรมเล่นเพลง” หรือ “เช็คระบบหลังบ้านหน่อย”</p>
            </div>
          ) : msgs.map(bubble)}
          {busy && !msgs.some(m => m.role === 'agent' && m.streaming) && (
            <motion.div 
              initial={{ opacity: 0, y: 5 }}
              animate={{ opacity: 1, y: 0 }}
              className="self-start glass-soft rounded-xl2 px-4 py-3 flex items-center gap-1.5 text-sm text-inkDim"
            >
              {[0, 1, 2].map((idx) => (
                <motion.span 
                  key={idx}
                  animate={{ y: [0, -4, 0] }}
                  transition={{
                    duration: 0.6,
                    repeat: Infinity,
                    delay: idx * 0.15,
                    ease: "easeInOut"
                  }}
                  className="w-2 h-2 rounded-full bg-accent inline-block" 
                />
              ))}
              <span className="ml-2">เอเจนต์กำลังคิดและวางแผนงาน...</span>
            </motion.div>
          )}
        </div>

        <form onSubmit={send} className="flex items-center gap-2 pt-3 border-t border-line">
          <input value={input} onChange={(e) => setInput(e.target.value)} disabled={busy}
            placeholder="พิมพ์สิ่งที่ต้องการให้ระบบทำ..."
            className="flex-1 bg-bg1/70 border border-line rounded-xl2 px-4 py-3 outline-none focus:border-accent transition disabled:opacity-60 text-sm" />
          <button type="submit" disabled={busy || !input.trim()}
            className="px-4 py-3 rounded-xl2 font-semibold text-bg0 disabled:opacity-60 transition hover:brightness-110 flex items-center gap-2 text-sm"
            style={{ background: 'linear-gradient(120deg,#00D4FF,#B44FFF)' }}>
            <Icon path={ICONS.send} className="w-4 h-4" /><span className="hidden sm:inline">ส่ง</span>
          </button>
        </form>
      </Card>

      {/* ฝั่งแดชบอร์ดแสดงผลกระบวนการทำงานเครื่องมือ (Timeline Flow) */}
      <Card className="p-4 sm:p-5 flex flex-col h-[50vh] lg:h-full border border-line overflow-hidden">
        <AgentStepsFlow steps={steps} />
      </Card>
    </div>
  );
}

// ── ตั้งค่าระบบ (schema-driven) — แก้ทุก knob ผ่านเว็บ แยกหมวด + ป้าย hot/restart ──
function SettingsPanel() {
  const [cats, setCats] = useState(null);
  const [draft, setDraft] = useState({});
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [confirmRestart, setConfirmRestart] = useState(false);
  const [restarting, setRestarting] = useState(false);

  const load = useCallback(async () => {
    setMsg(null);
    try {
      const d = await api('/admin/api/settings/all');
      setCats(d.categories || []);
      const init = {};
      (d.categories || []).forEach((c) => c.fields.forEach((f) => {
        init[f.key] = f.type === 'bool' ? (String(f.value).toLowerCase() === 'true') : (f.value || '');
      }));
      setDraft(init);
    } catch (e) { if (e.message !== 'unauthorized') setMsg({ ok: false, text: e.message }); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const setVal = (k, v) => setDraft((d) => ({ ...d, [k]: v }));

  const save = async () => {
    setBusy(true); setMsg(null);
    try {
      const values = {};
      Object.keys(draft).forEach((k) => { values[k] = typeof draft[k] === 'boolean' ? String(draft[k]) : draft[k]; });
      const r = await api('/admin/api/settings/all', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ values }),
      });
      if (r.restart_needed) { setConfirmRestart(true); setMsg({ ok: true, text: 'บันทึกแล้ว — บางค่าต้อง restart ถึงจะมีผล' }); }
      else setMsg({ ok: true, text: (r.changed && r.changed.length) ? '✓ บันทึกแล้ว มีผลทันที' : 'ไม่มีอะไรเปลี่ยน' });
      setTimeout(load, 600);
    } catch (e) { if (e.message !== 'unauthorized') setMsg({ ok: false, text: 'บันทึกล้มเหลว: ' + e.message }); }
    finally { setBusy(false); }
  };

  const doRestart = async () => {
    setRestarting(true);
    try { await api('/admin/api/restart', { method: 'POST' }); } catch (_) {}
    setTimeout(() => window.location.reload(), 6000); // server หลุดชั่วครู่ตอน re-exec → รอแล้วรีโหลด
  };

  if (cats === null) return <Card className="p-5"><Spinner text="กำลังโหลดการตั้งค่า..." /></Card>;

  const inputCls = 'w-full bg-bg1/70 border border-line rounded-lg px-3 py-2 text-sm outline-none focus:border-accent transition';
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-semibold">ตั้งค่าระบบ (Settings)</h2>
        <button onClick={load} className="w-8 h-8 flex items-center justify-center rounded-lg text-inkDim hover:text-accent hover:bg-white/5 transition">
          <Icon path={ICONS.refresh} className="w-4 h-4" />
        </button>
      </div>

      <div className="flex flex-col gap-5">
        {cats.map((cat) => (
          <div key={cat.id}>
            <div className="text-xs uppercase tracking-wide text-accent2 font-semibold mb-2">{cat.label}</div>
            <div className="grid sm:grid-cols-2 gap-3">
              {cat.fields.map((f) => (
                <div key={f.key} className="glass-soft rounded-xl2 p-3 border border-line/60">
                  <div className="flex items-center justify-between gap-2 mb-1.5">
                    <label className="text-xs text-ink font-medium">{f.label}</label>
                    {f.hot ? <Badge color="accent">ทันที</Badge> : <Badge color="accent2">restart</Badge>}
                  </div>
                  {f.type === 'bool' ? (
                    <label className="flex items-center gap-2 text-xs text-inkDim cursor-pointer select-none">
                      <input type="checkbox" checked={!!draft[f.key]} onChange={(e) => setVal(f.key, e.target.checked)} />
                      {draft[f.key] ? 'เปิด' : 'ปิด'}
                    </label>
                  ) : (
                    <input
                      type={f.secret ? 'password' : (f.type === 'int' ? 'number' : 'text')}
                      value={draft[f.key] ?? ''}
                      onChange={(e) => setVal(f.key, e.target.value)}
                      placeholder={f.secret ? (f.isSet ? '(ตั้งไว้แล้ว — เว้นว่าง=ไม่เปลี่ยน)' : 'ยังไม่ได้ตั้ง') : ''}
                      className={inputCls + (f.secret ? ' font-mono' : '')} />
                  )}
                  {f.help && <div className="text-[10px] text-inkXdim mt-1">{f.help}</div>}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {msg && <div className={'text-xs text-center mt-4 ' + (msg.ok ? 'text-ok' : 'text-danger')}>{msg.text}</div>}

      <div className="flex gap-2 mt-4">
        <button onClick={save} disabled={busy}
          className="flex-1 py-2.5 rounded-xl2 font-semibold text-bg0 disabled:opacity-60 transition hover:brightness-110 text-sm"
          style={{ background: 'linear-gradient(120deg,#00D4FF,#B44FFF)' }}>
          {busy ? 'กำลังบันทึก...' : 'บันทึกการตั้งค่า'}
        </button>
        <button onClick={() => setConfirmRestart(true)} disabled={busy}
          className="px-4 py-2.5 rounded-xl2 text-sm border border-line text-inkDim hover:text-accent hover:bg-white/5 transition">
          Restart Hub
        </button>
      </div>

      {confirmRestart && (
        <div className="fixed inset-0 z-50 bg-bg0/80 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => !restarting && setConfirmRestart(false)}>
          <div className="glass rounded-xl2 w-full max-w-sm p-6 text-center" onClick={(e) => e.stopPropagation()}>
            {restarting ? (
              <Spinner text="กำลัง restart Hub... หน้าจะรีโหลดเองใน ~6 วิ" />
            ) : (
              <>
                <div className="text-3xl mb-2">♻️</div>
                <h3 className="font-semibold text-ink mb-1">Restart Hub?</h3>
                <p className="text-xs text-inkDim mb-5">ค่าที่ติดป้าย “restart” จะมีผลหลังรีสตาร์ท · ระหว่างนั้น Hub จะออฟไลน์ชั่วครู่</p>
                <div className="flex gap-2">
                  <button onClick={() => setConfirmRestart(false)}
                    className="flex-1 py-2.5 rounded-xl2 text-sm border border-line text-inkDim hover:bg-white/5 transition">ยกเลิก</button>
                  <button onClick={doRestart}
                    className="flex-1 py-2.5 rounded-xl2 text-sm font-semibold text-bg0 hover:brightness-110 transition"
                    style={{ background: 'linear-gradient(120deg,#00D4FF,#B44FFF)' }}>Restart เลย</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
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
    <div className="flex flex-col gap-4">
      <SettingsPanel />
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
// โชว์พิกัด lat/lng ของทุกคนบนแผนที่เดียวแบบ Premium Dark Theme
// พร้อมหน้าต่างควบคุมสำหรับเลือกส่งคำสั่ง/ข้อความหาแอปนั้นๆ โดยตรง
const gmapsLink = (lat, lng) => `https://www.google.com/maps?q=${lat},${lng}`;

function LocationTab({ users, liveUpdate, activeTab }) {
  const [locs, setLocs] = useState({}); // uid → phone data
  const [loading, setLoading] = useState(true);
  const [selectedUid, setSelectedUid] = useState(null);
  const [msgText, setMsgText] = useState('');
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState(null);

  const mapRef = useRef(null);
  const containerRef = useRef(null);
  const markersRef = useRef({});
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

  // อัปเดตพิกัดสด
  useEffect(() => {
    if (liveUpdate && liveUpdate.kind === 'phone') {
      setLocs((prev) => ({ ...prev, [liveUpdate.user_id]: liveUpdate.data }));
    }
  }, [liveUpdate]);

  // รีเฟรชแผนที่เมื่อสลับแท็บกลับมา
  useEffect(() => {
    if (activeTab === 'location' && mapRef.current) {
      setTimeout(() => {
        if (mapRef.current) {
          mapRef.current.invalidateSize({ animate: true });
          // จัดมุมกล้องให้ครอบคลุมทุกคนถ้าไม่ได้เจาะจงใคร
          if (!selectedUid) {
            const bounds = [];
            Object.values(locs).forEach((phone) => {
              if (phone && typeof phone.lat === 'number' && typeof phone.lng === 'number') {
                bounds.push([phone.lat, phone.lng]);
              }
            });
            if (bounds.length > 0) {
              mapRef.current.fitBounds(bounds, { padding: [50, 50], maxZoom: 17 });
            }
          }
        }
      }, 100);
    }
  }, [activeTab, locs, selectedUid]);

  // สร้างแผนที่ Leaflet
  useEffect(() => {
    if (!window.L || !containerRef.current) return;

    if (!mapRef.current) {
      const map = L.map(containerRef.current, {
        center: [13.7563, 100.5018],
        zoom: 6,
        zoomControl: false
      });
      L.control.zoom({ position: 'topright' }).addTo(map);

      const retina = L.Browser.retina ? '@2x' : ''; // จอความละเอียดสูง → tile คมขึ้น

      // ── ฐานแผนที่พรีเมียม (ทุกตัวฟรี ไม่ต้องใช้ API key) ──
      // มืด (ดีฟอลต์) — CartoDB dark คมเข้มแบบ premium
      const dark = L.tileLayer(`https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}${retina}.png`, {
        attribution: '&copy; OpenStreetMap &copy; CARTO', subdomains: 'abcd', maxZoom: 20
      });
      // สว่าง — CartoDB Voyager (สีนุ่ม อ่านง่าย สไตล์พรีเมียม)
      const voyager = L.tileLayer(`https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}${retina}.png`, {
        attribution: '&copy; OpenStreetMap &copy; CARTO', subdomains: 'abcd', maxZoom: 20
      });
      // ดาวเทียม — ภาพถ่าย Esri + ป้ายชื่อสถานที่ (ฟีลพรีเมียมแบบ Google/Life360)
      // Esri มีภาพถึง z19 — เกินนั้น (z20) จะส่ง placeholder "Map data not yet available"
      // → maxNativeZoom:19 ให้ Leaflet ดึง z19 มาขยายเองตอนซูม 20 (ไม่ขึ้นรูปเทา)
      const satellite = L.layerGroup([
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
          attribution: 'Imagery &copy; Esri', maxZoom: 20, maxNativeZoom: 19
        }),
        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
          maxZoom: 20, maxNativeZoom: 19
        })
      ]);

      dark.addTo(map); // โหมดเริ่มต้น

      // ตัวสลับโหมดแผนที่ (มุมขวาบน)
      L.control.layers(
        { '🌙 มืด': dark, '☀️ สว่าง': voyager, '🛰️ ดาวเทียม': satellite },
        null,
        { position: 'topright', collapsed: true }
      ).addTo(map);

      mapRef.current = map;
    }

    if (loading) return;

    const map = mapRef.current;

    // เคลียร์หมุดเก่า
    Object.values(markersRef.current).forEach((m) => m.remove());
    markersRef.current = {};

    const bounds = [];
    Object.entries(locs).forEach(([uid, phone]) => {
      if (!phone || typeof phone.lat !== 'number' || typeof phone.lng !== 'number') return;
      const lat = phone.lat;
      const lng = phone.lng;
      bounds.push([lat, lng]);

      const user = users[uid] || {};
      const name = user.displayName || user.app_name || 'ผู้ใช้แอป';
      const moving = phone.moving;
      const bat = phone.level !== undefined ? `${phone.level}%` : '';

      const customIcon = L.divIcon({
        html: `
          <div class="relative flex flex-col items-center">
            ${moving ? '<span class="absolute top-1 inline-flex h-6 w-6 rounded-full bg-cyan-400/40 animate-ping"></span>' : ''}
            <div class="w-3.5 h-3.5 rounded-full bg-gradient-to-r from-[#00D4FF] to-[#B44FFF] border-2 border-[#080B12] shadow-md relative z-10 flex items-center justify-center">
              <div class="w-1.5 h-1.5 rounded-full bg-white"></div>
            </div>
            <div class="mt-1 px-2 py-0.5 rounded-md bg-[#10141F]/90 border border-[#2A3142] text-[10px] font-semibold text-[#EEF1F5] shadow-md whitespace-nowrap select-none">
              ${name}${bat ? ` 🔋${bat}` : ''}
            </div>
          </div>
        `,
        className: 'custom-leaflet-marker',
        iconSize: [60, 40],
        iconAnchor: [30, 7]
      });

      const marker = L.marker([lat, lng], { icon: customIcon }).addTo(map);
      marker.on('click', () => {
        setSelectedUid(uid);
        setSendResult(null);
        map.setView([lat, lng], Math.max(map.getZoom(), 14), { animate: true });
      });
      markersRef.current[uid] = marker;
    });

    if (bounds.length > 0 && !selectedUid) {
      map.fitBounds(bounds, { padding: [50, 50], maxZoom: 17 });
    }
  }, [loading, locs, users]);

  // ซูมเข้าหาผู้ใช้ที่ถูกเลือก
  useEffect(() => {
    if (selectedUid && mapRef.current) {
      const phone = locs[selectedUid];
      if (phone && typeof phone.lat === 'number' && typeof phone.lng === 'number') {
        mapRef.current.setView([phone.lat, phone.lng], Math.max(mapRef.current.getZoom(), 14), { animate: true });
      }
    }
  }, [selectedUid, locs]);

  // ส่งข้อความ/คำสั่งหาแอปผ่าน FCM
  const sendMessage = async (e) => {
    e.preventDefault();
    if (!selectedUid || !msgText.trim() || sending) return;
    setSending(true);
    setSendResult(null);
    try {
      const res = await api(`/admin/api/users/${selectedUid}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msgText.trim() })
      });
      setSendResult({ ok: true, text: `✓ ${res.result || 'ส่งสำเร็จ'}` });
      setMsgText('');
    } catch (err) {
      setSendResult({ ok: false, text: `✗ ส่งไม่สำเร็จ: ${err.message}` });
    } finally {
      setSending(false);
    }
  };

  const selectedUser = users[selectedUid];
  const selectedPhone = locs[selectedUid];
  const hasGps = selectedPhone && typeof selectedPhone.lat === 'number' && typeof selectedPhone.lng === 'number';

  return (
    <div className="flex flex-col gap-4">
      <style>{`
        .leaflet-container {
          background-color: #080B12 !important;
          font-family: inherit !important;
        }
        .leaflet-bar {
          border: 1px solid rgba(42, 49, 66, 0.6) !important;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25) !important;
          border-radius: 8px !important;
          overflow: hidden;
        }
        .leaflet-bar a {
          background-color: rgba(20, 25, 37, 0.9) !important;
          color: #EEF1F5 !important;
          border-bottom: 1px solid rgba(42, 49, 66, 0.6) !important;
          transition: all 0.2s;
        }
        .leaflet-bar a:hover {
          background-color: #00D4FF !important;
          color: #080B12 !important;
        }
        .leaflet-popup-content-wrapper {
          background: rgba(26, 32, 48, 0.9) !important;
          backdrop-filter: blur(12px) !important;
          border: 1px solid rgba(58, 66, 86, 0.6) !important;
          color: #EEF1F5 !important;
          border-radius: 12px !important;
        }
        .leaflet-popup-tip {
          background: rgba(26, 32, 48, 0.9) !important;
        }
        .leaflet-control-layers {
          background: rgba(20, 25, 37, 0.92) !important;
          backdrop-filter: blur(12px) !important;
          border: 1px solid rgba(42, 49, 66, 0.6) !important;
          border-radius: 10px !important;
          box-shadow: 0 4px 14px rgba(0, 0, 0, 0.3) !important;
          color: #EEF1F5 !important;
        }
        .leaflet-control-layers-toggle {
          background-color: rgba(20, 25, 37, 0.92) !important;
          border-radius: 10px !important;
          width: 36px !important;
          height: 36px !important;
        }
        .leaflet-control-layers-expanded {
          padding: 10px 12px !important;
        }
        .leaflet-control-layers label {
          font-size: 13px !important;
          margin: 4px 0 !important;
          cursor: pointer;
        }
        .leaflet-control-layers-selector {
          accent-color: #00D4FF;
          margin-right: 6px !important;
        }
        .leaflet-control-attribution {
          background: rgba(8, 11, 18, 0.7) !important;
          color: #6b7280 !important;
        }
        .leaflet-control-attribution a { color: #9aa4b2 !important; }
      `}</style>

      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-lg flex items-center gap-2">
          <span>📍</span> แผนที่ระบบระบุตำแหน่งรวม (Unified GPS Dashboard)
        </h2>
        <button onClick={loadAll} title="โหลดข้อมูลทั้งหมดใหม่"
          className="w-9 h-9 flex items-center justify-center rounded-xl2 bg-white/5 text-inkDim hover:text-accent hover:bg-white/10 transition border border-line">
          <Icon path={ICONS.refresh} className="w-4 h-4" />
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_380px] gap-5">
        {/* ส่วนแสดงแผนที่ Leaflet */}
        <Card className="p-2 relative h-[50vh] lg:h-[68vh] overflow-hidden flex flex-col border border-line">
          {loading && (
            <div className="absolute inset-0 z-20 bg-bg0/80 backdrop-blur-sm flex items-center justify-center rounded-xl2">
              <Spinner text="กำลังโหลดแผนที่และพิกัดผู้ใช้..." />
            </div>
          )}
          <div ref={containerRef} className="w-full h-full rounded-xl2" style={{ minHeight: '350px' }} />
        </Card>

          {/* แผงควบคุมและส่งข้อความหาแอป */}
          <Card className="p-5 flex flex-col justify-between h-fit lg:h-[68vh] border border-line gap-4 font-sans">
            {!selectedUid ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center py-10 text-inkDim gap-4 fade-in">
                <div className="w-16 h-16 rounded-2xl bg-accent/10 border border-accent/20 flex items-center justify-center text-accent text-3xl">📍</div>
                <div>
                  <div className="font-semibold text-ink text-base">คลิกเลือกผู้ใช้งาน</div>
                  <p className="text-xs mt-1 text-inkDim max-w-[280px]">
                    จิ้มที่หมุดบนแผนที่ หรือเลือกรายชื่อผู้ใช้ด้านล่าง เพื่อดูรายละเอียดเชิงลึกและส่งข้อความหาผู้ช่วยได้ทันทีค่ะ
                  </p>
                </div>

                <div className="w-full border-t border-line mt-4 pt-4 flex flex-col gap-2 max-h-[30vh] overflow-y-auto">
                  <div className="text-[11px] uppercase tracking-wide text-accent font-semibold text-left mb-1">รายชื่อผู้ใช้ระบบในปัจจุบัน</div>
                  {ids.length === 0 ? (
                    <div className="text-xs text-inkXdim py-4">ยังไม่มีผู้ใช้งานลงทะเบียน</div>
                  ) : (
                    ids.map((uid) => {
                      const user = users[uid] || {};
                      const phone = locs[uid];
                      const activeGPS = phone && typeof phone.lat === 'number' && typeof phone.lng === 'number';
                      return (
                        <button key={uid} onClick={() => setSelectedUid(uid)}
                          className="flex items-center justify-between p-3 rounded-xl2 bg-bg1/40 hover:bg-white/5 border border-line text-left transition text-xs">
                          <span className="font-medium text-ink truncate max-w-[170px]">{user.displayName || user.app_name || 'แอปนิรนาม'}</span>
                          <span className={activeGPS ? 'text-ok font-semibold' : 'text-inkXdim'}>
                            {activeGPS ? '📍 มีพิกัด' : '❌ ไม่มีพิกัด'}
                          </span>
                        </button>
                      );
                    })
                  )}
                </div>
              </div>
            ) : (
              <div className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-4 fade-in pr-1">
                {/* ข้อมูลผู้ใช้ */}
                <div className="flex flex-col gap-3.5">
                  <div className="flex justify-between items-start border-b border-line pb-3">
                    <div className="min-w-0">
                      <h3 className="font-semibold text-ink text-base truncate">{(selectedUser && selectedUser.displayName) || (selectedUser && selectedUser.app_name) || 'แอปนิรนาม'}</h3>
                      <p className="text-[10px] text-inkDim font-mono truncate mt-0.5">{selectedUid}</p>
                    </div>
                    <button onClick={() => { setSelectedUid(null); setSendResult(null); }}
                      className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-white/10 text-inkDim hover:text-ink transition border border-line text-xs font-semibold">
                      ✕
                    </button>
                  </div>

                  {hasGps ? (
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="glass-soft rounded-xl2 p-3 border border-line">
                        <div className="text-[10px] uppercase tracking-wide text-accent font-medium mb-1">Latitude</div>
                        <div className="font-mono text-ink text-sm font-semibold">{selectedPhone.lat.toFixed(6)}</div>
                      </div>
                      <div className="glass-soft rounded-xl2 p-3 border border-line">
                        <div className="text-[10px] uppercase tracking-wide text-accent font-medium mb-1">Longitude</div>
                        <div className="font-mono text-ink text-sm font-semibold">{selectedPhone.lng.toFixed(6)}</div>
                      </div>
                    </div>
                  ) : (
                    <div className="text-xs bg-danger/10 border border-danger/20 rounded-xl2 p-3 text-danger text-center">
                      ⚠️ ยังไม่ได้รับพิกัด GPS ปัจจุบันของผู้ใช้คนนี้
                    </div>
                  )}

                  {/* สรุปสถานะทางร่างกายและมือถือ */}
                  <div className="glass-soft rounded-xl2 p-3 border border-line flex flex-col gap-2 text-xs text-inkDim">
                    <div className="flex justify-between">
                      <span>สถานะการเคลื่อนที่:</span>
                      <span className="font-semibold">
                        {selectedPhone && selectedPhone.moving ? (
                          <Badge color="accent">กำลังเคลื่อนไหว 🏃</Badge>
                        ) : (
                          <Badge color="dim">อยู่นิ่ง 📍</Badge>
                        )}
                      </span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span>ระดับแบตเตอรี่:</span>
                      <span className="font-semibold text-ink">
                        🔋 {selectedPhone && selectedPhone.level !== undefined ? `${selectedPhone.level}%` : '—'}
                        {selectedPhone && selectedPhone.charging ? ' ⚡ (ชาร์จอยู่)' : ''}
                      </span>
                    </div>
                    {hasGps && (
                      <div className="flex justify-end mt-1 border-t border-line/40 pt-2">
                        <a href={gmapsLink(selectedPhone.lat, selectedPhone.lng)} target="_blank" rel="noreferrer"
                          className="text-accent hover:underline text-[11px] font-semibold flex items-center gap-1">
                          🌐 เปิดดูบน Google Maps →
                        </a>
                      </div>
                    )}
                  </div>
                </div>

                {/* กล่องส่ง FCM ถึงแอป */}
                <form onSubmit={sendMessage} className="flex flex-col gap-3 border-t border-line pt-4">
                  <div className="text-xs uppercase tracking-wide text-accent2 font-semibold">💬 ส่งข้อความหาผู้ช่วยของผู้ใช้คนนี้</div>

                  <textarea value={msgText} onChange={(e) => setMsgText(e.target.value)} disabled={sending}
                    placeholder="พิมพ์ข้อความหรือสิ่งที่อยากให้ผู้ช่วยทำ..." rows={3}
                    className="w-full bg-bg1/70 border border-line rounded-xl2 px-3.5 py-2.5 outline-none focus:border-accent2 transition text-xs text-ink placeholder:text-inkXdim disabled:opacity-60 resize-none" />

                  {sendResult && (
                    <div className={`text-[11px] text-center p-2 rounded-lg font-medium ${sendResult.ok ? 'bg-ok/10 text-ok border border-ok/20' : 'bg-danger/10 text-danger border border-danger/20'}`}>
                      {sendResult.text}
                    </div>
                  )}

                  <button type="submit" disabled={sending || !msgText.trim()}
                    className="w-full py-2.5 rounded-xl2 font-semibold text-bg0 disabled:opacity-50 transition hover:brightness-110 flex items-center justify-center gap-1 text-xs"
                    style={{ background: 'linear-gradient(120deg,#00D4FF,#B44FFF)' }}>
                    {sending ? (
                      <>
                        <span className="w-3.5 h-3.5 border-2 border-bg0/40 border-t-bg0 rounded-full animate-spin"></span>
                        <span>กำลังนำส่ง...</span>
                      </>
                    ) : (
                      <span>🚀 ส่งข้อความหาแอป</span>
                    )}
                  </button>
                </form>
              </div>
            )}
          </Card>
        </div>
    </div>
  );
}

// ── แอปหลัก ─────────────────────────────────────────────────────────────────
// ── แท็บ: กฎอัตโนมัติ (event rules บน Hub) ──────────────────────────────────
const SPECIAL_SOURCES = [
  { v: '__time__', label: '⏰ เวลา (HH:MM)' },
  { v: '__weekday__', label: '📅 วัน (mon,tue,..)' },
  { v: '__battery__', label: '🔋 แบตมือถือ (%)' },
  { v: '__charging__', label: '⚡ กำลังชาร์จ (true/false)' },
];
const OPS = ['>', '<', '>=', '<=', '==', '!='];

function condText(c, devs) {
  const d = (devs || []).find((x) => x.topic === c.source || 'online:' + x.topic === c.source);
  const name = c.source.startsWith('online:') ? `${d ? d.name : c.source.slice(7)} ออนไลน์?`
    : c.source === '__time__' ? 'เวลา' : c.source === '__weekday__' ? 'วัน'
    : c.source === '__battery__' ? 'แบตมือถือ' : c.source === '__charging__' ? 'กำลังชาร์จ'
    : (d ? d.name : c.source);
  return `${name} ${c.op} ${c.value}`;
}

function actText(a, devs) {
  if (a.kind === 'device') {
    const d = (devs || []).find((x) => x.topic === a.topic);
    return `สั่ง ${d ? d.name : a.topic} = ${a.value}`;
  }
  if (a.kind === 'notify') return `แจ้งเตือน: "${(a.text || '').slice(0, 50)}"`;
  if (a.kind === 'agent') return `ให้สมองทำ: "${(a.task || '').slice(0, 50)}"`;
  if (a.kind === 'scene') return `เปิด scene ${a.scene_id}`;
  return a.kind;
}

function RuleForm({ devs, users, onSaved, onCancel }) {
  const [name, setName] = useState('');
  const [logic, setLogic] = useState('AND');
  const [cooldown, setCooldown] = useState(60);
  const [once, setOnce] = useState(false);
  const [userId, setUserId] = useState('');
  const [conds, setConds] = useState([{ source: '', op: '>', value: '' }]);
  const [acts, setActs] = useState([{ kind: 'device', topic: '', value: 'true', text: '', task: '' }]);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');

  const setCond = (i, k, v) => setConds(conds.map((c, j) => (j === i ? { ...c, [k]: v } : c)));
  const setAct = (i, k, v) => setActs(acts.map((a, j) => (j === i ? { ...a, [k]: v } : a)));

  const save = async () => {
    setErr('');
    const conditions = conds.filter((c) => c.source && c.value !== '');
    if (!conditions.length) { setErr('ต้องมีเงื่อนไขอย่างน้อย 1 ข้อ'); return; }
    const actions = acts.map((a) => {
      if (a.kind === 'device') return a.topic ? { kind: 'device', topic: a.topic, value: a.value } : null;
      if (a.kind === 'notify') return a.text ? { kind: 'notify', text: a.text } : null;
      if (a.kind === 'agent') return a.task ? { kind: 'agent', task: a.task } : null;
      return null;
    }).filter(Boolean);
    if (!actions.length) { setErr('ต้องมี action อย่างน้อย 1 อย่าง'); return; }
    setSaving(true);
    try {
      await api('/admin/api/rules', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, logic, conditions, actions, cooldown_sec: cooldown, once, user_id: userId }),
      });
      onSaved();
    } catch (e) { setErr(e.message); }
    setSaving(false);
  };

  const inputCls = 'bg-bg1/70 border border-line rounded-lg px-2.5 py-1.5 text-sm focus:border-accent outline-none';
  return (
    <Card className="p-5 border border-accent/30">
      <h3 className="font-semibold mb-4">สร้างกฎใหม่</h3>
      <div className="flex flex-wrap gap-3 mb-4 items-center">
        <input className={inputCls + ' flex-1 min-w-[200px]'} placeholder="ชื่อกฎ เช่น ร้อนเกินเปิดพัดลม" value={name} onChange={(e) => setName(e.target.value)} />
        <select className={inputCls} value={userId} onChange={(e) => setUserId(e.target.value)}>
          <option value="">เจ้าของกฎ (สำหรับแจ้งเตือน)</option>
          {Object.entries(users || {}).map(([uid, u]) => <option key={uid} value={uid}>{(u && u.app_name) || uid}</option>)}
        </select>
      </div>

      <div className="text-xs text-inkDim mb-1.5">เงื่อนไข (ครบตามนี้แล้วกฎจะยิง)</div>
      {conds.map((c, i) => (
        <div key={i} className="flex flex-wrap gap-2 mb-2 items-center">
          <select className={inputCls + ' min-w-[180px]'} value={c.source} onChange={(e) => setCond(i, 'source', e.target.value)}>
            <option value="">— เลือกแหล่งเงื่อนไข —</option>
            <optgroup label="อุปกรณ์ (ค่าปัจจุบัน)">
              {(devs || []).map((d) => <option key={d.topic} value={d.topic}>{d.name} ({d.type})</option>)}
            </optgroup>
            <optgroup label="อุปกรณ์ออนไลน์/ออฟไลน์">
              {(devs || []).map((d) => <option key={'o' + d.topic} value={'online:' + d.topic}>{d.name} ออนไลน์?</option>)}
            </optgroup>
            <optgroup label="ค่าระบบ">
              {SPECIAL_SOURCES.map((s) => <option key={s.v} value={s.v}>{s.label}</option>)}
            </optgroup>
          </select>
          <select className={inputCls} value={c.op} onChange={(e) => setCond(i, 'op', e.target.value)}>
            {OPS.map((o) => <option key={o}>{o}</option>)}
          </select>
          <input className={inputCls + ' w-36'} placeholder="ค่า เช่น 30 / online" value={c.value} onChange={(e) => setCond(i, 'value', e.target.value)} />
          {conds.length > 1 && <button className="text-danger text-sm px-1" onClick={() => setConds(conds.filter((_, j) => j !== i))}>✕</button>}
        </div>
      ))}
      <div className="flex gap-3 items-center mb-4">
        <button className="text-xs text-accent hover:underline" onClick={() => setConds([...conds, { source: '', op: '>', value: '' }])}>+ เพิ่มเงื่อนไข</button>
        {conds.length > 1 && (
          <select className={inputCls + ' text-xs'} value={logic} onChange={(e) => setLogic(e.target.value)}>
            <option value="AND">ต้องจริงทุกข้อ (AND)</option>
            <option value="OR">จริงข้อใดข้อหนึ่ง (OR)</option>
          </select>
        )}
      </div>

      <div className="text-xs text-inkDim mb-1.5">สิ่งที่จะทำ</div>
      {acts.map((a, i) => (
        <div key={i} className="flex flex-wrap gap-2 mb-2 items-center">
          <select className={inputCls} value={a.kind} onChange={(e) => setAct(i, 'kind', e.target.value)}>
            <option value="device">สั่งอุปกรณ์</option>
            <option value="notify">แจ้งเตือนเข้ามือถือ</option>
            <option value="agent">ให้สมอง (AI) ทำ</option>
          </select>
          {a.kind === 'device' && (
            <React.Fragment>
              <select className={inputCls + ' min-w-[160px]'} value={a.topic} onChange={(e) => setAct(i, 'topic', e.target.value)}>
                <option value="">— เลือกอุปกรณ์ —</option>
                {(devs || []).filter((d) => d.type !== 'sensor').map((d) => <option key={d.topic} value={d.topic}>{d.name}</option>)}
              </select>
              <input className={inputCls + ' w-28'} placeholder="true/false/0-255" value={a.value} onChange={(e) => setAct(i, 'value', e.target.value)} />
            </React.Fragment>
          )}
          {a.kind === 'notify' && <input className={inputCls + ' flex-1 min-w-[220px]'} placeholder="ข้อความแจ้งเตือน" value={a.text} onChange={(e) => setAct(i, 'text', e.target.value)} />}
          {a.kind === 'agent' && <input className={inputCls + ' flex-1 min-w-[220px]'} placeholder="งานที่ให้ AI ทำ เช่น สรุปสถานะบ้านแล้วแจ้งเจ้าของ" value={a.task} onChange={(e) => setAct(i, 'task', e.target.value)} />}
          {acts.length > 1 && <button className="text-danger text-sm px-1" onClick={() => setActs(acts.filter((_, j) => j !== i))}>✕</button>}
        </div>
      ))}
      <button className="text-xs text-accent hover:underline mb-4" onClick={() => setActs([...acts, { kind: 'device', topic: '', value: 'true', text: '', task: '' }])}>+ เพิ่ม action</button>

      <div className="flex flex-wrap gap-3 items-center border-t border-line pt-4">
        <label className="text-xs text-inkDim flex items-center gap-2">กันยิงรัว (วินาที)
          <input type="number" className={inputCls + ' w-20'} value={cooldown} onChange={(e) => setCooldown(parseInt(e.target.value) || 0)} />
        </label>
        <label className="text-xs text-inkDim flex items-center gap-1.5">
          <input type="checkbox" checked={once} onChange={(e) => setOnce(e.target.checked)} /> ยิงครั้งเดียวแล้วปิดกฎ
        </label>
        <div className="ml-auto flex gap-2">
          <button onClick={onCancel} className="px-4 py-2 rounded-xl2 text-sm text-inkDim hover:text-ink border border-line">ยกเลิก</button>
          <button onClick={save} disabled={saving} className="px-4 py-2 rounded-xl2 text-sm font-medium bg-accent/15 text-accent hover:bg-accent/25 disabled:opacity-50">
            {saving ? 'กำลังบันทึก...' : 'บันทึกกฎ'}
          </button>
        </div>
      </div>
      {err && <div className="text-danger text-sm mt-2">{err}</div>}
    </Card>
  );
}

function RulesTab({ users }) {
  const [rules, setRules] = useState(null);
  const [devs, setDevs] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    setErr('');
    try {
      const [r, d] = await Promise.all([api('/admin/api/rules'), api('/admin/api/devices')]);
      setRules(r); setDevs(d);
    } catch (e) { if (e.message !== 'unauthorized') setErr(e.message); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const toggle = async (r) => {
    await api(`/admin/api/rules/${r.id}/toggle`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: !r.enabled }) });
    load();
  };
  const del = async (r) => {
    if (!confirm(`ลบกฎ «${r.name}» ?`)) return;
    await api(`/admin/api/rules/${r.id}`, { method: 'DELETE' });
    load();
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-lg">กฎอัตโนมัติของ Hub <span className="text-inkDim text-sm font-normal">· ทำงานตลอด 24 ชม. แม้มือถือปิด</span></h2>
        <div className="flex gap-2">
          <button onClick={load} className="w-9 h-9 flex items-center justify-center rounded-lg text-inkDim hover:text-accent hover:bg-white/5"><Icon path={ICONS.refresh} className="w-4 h-4" /></button>
          <button onClick={() => setShowForm(!showForm)} className="px-4 py-2 rounded-xl2 text-sm font-medium bg-accent/15 text-accent hover:bg-accent/25">{showForm ? 'ปิดฟอร์ม' : '+ สร้างกฎ'}</button>
        </div>
      </div>

      {showForm && <RuleForm devs={devs} users={users} onSaved={() => { setShowForm(false); load(); }} onCancel={() => setShowForm(false)} />}

      {err ? <Spinner text={'โหลดล้มเหลว: ' + err} danger /> : rules === null ? <Spinner />
        : rules.length === 0 ? <Card className="p-8 text-center text-inkDim text-sm">ยังไม่มีกฎ — กด "+ สร้างกฎ" หรือสั่งซินจากมือถือ เช่น "ถ้าอุณหภูมิเกิน 30 เปิดพัดลม"</Card>
        : rules.map((r) => (
          <Card key={r.id} className={'p-4 ' + (r.enabled ? '' : 'opacity-50')}>
            <div className="flex flex-wrap items-center gap-3">
              <button onClick={() => toggle(r)} title={r.enabled ? 'กดเพื่อปิด' : 'กดเพื่อเปิด'}
                className={'w-10 h-6 rounded-full relative transition ' + (r.enabled ? 'bg-ok/70' : 'bg-inkXdim/40')}>
                <span className={'absolute top-0.5 w-5 h-5 rounded-full bg-white transition-all ' + (r.enabled ? 'left-[18px]' : 'left-0.5')} />
              </button>
              <div className="flex-1 min-w-[220px]">
                <div className="font-medium">{r.name} {r.once && <Badge color="accent2">ครั้งเดียว</Badge>}</div>
                <div className="text-sm text-inkDim mt-0.5">
                  ถ้า {(r.conditions || []).map((c) => condText(c, devs)).join(r.logic === 'OR' ? ' หรือ ' : ' และ ')}
                  <span className="text-accent"> → </span>
                  {(r.actions || []).map((a) => actText(a, devs)).join(' · ')}
                </div>
              </div>
              <div className="text-xs text-inkXdim text-right">
                <div>กันยิงรัว {r.cooldown_sec || 0} วิ</div>
                <div>{r.last_fired ? 'ยิงล่าสุด ' + thDate(r.last_fired) : 'ยังไม่เคยยิง'}</div>
              </div>
              <button onClick={() => del(r)} className="text-danger/70 hover:text-danger text-sm px-2">ลบ</button>
            </div>
          </Card>
        ))}
    </div>
  );
}

// ── แท็บ: งานตั้งเวลา (automation jobs ของ Hub) ─────────────────────────────
function JobsTab({ users }) {
  const [jobs, setJobs] = useState(null);
  const [err, setErr] = useState('');
  const [task, setTask] = useState('');
  const [mode, setMode] = useState('delay');
  const [value, setValue] = useState('');
  const [userId, setUserId] = useState('');
  const [msg, setMsg] = useState('');

  const load = useCallback(async () => {
    setErr('');
    try { setJobs(await api('/admin/api/jobs')); }
    catch (e) { if (e.message !== 'unauthorized') setErr(e.message); }
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, [load]);

  const add = async () => {
    setMsg('');
    try {
      const r = await api('/admin/api/jobs', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task, mode, value, user_id: userId }),
      });
      setMsg(r.message); setTask(''); setValue(''); load();
    } catch (e) { setMsg(e.message); }
  };
  const del = async (j) => {
    if (!confirm(`ยกเลิกงาน «${j.name}» ?`)) return;
    await api(`/admin/api/jobs/${j.id}`, { method: 'DELETE' });
    load();
  };

  const inputCls = 'bg-bg1/70 border border-line rounded-lg px-2.5 py-1.5 text-sm focus:border-accent outline-none';
  const modeHint = mode === 'at' ? 'เวลา ISO เช่น 2026-06-12T18:30' : 'วินาที เช่น 3600';
  return (
    <div className="flex flex-col gap-4">
      <h2 className="font-semibold text-lg">งานตั้งเวลาของ Hub <span className="text-inkDim text-sm font-normal">· สมอง (AI) ลงมือทำตามกำหนด แล้วรายงานผลเข้ามือถือ</span></h2>

      <Card className="p-5">
        <div className="flex flex-wrap gap-2 items-center">
          <input className={inputCls + ' flex-1 min-w-[260px]'} placeholder='งานที่ให้ทำ เช่น "สรุปพื้นที่ disk ที่เหลือ แล้วแจ้งผล"' value={task} onChange={(e) => setTask(e.target.value)} />
          <select className={inputCls} value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="delay">อีก N วินาที (ครั้งเดียว)</option>
            <option value="at">เวลาที่กำหนด (ครั้งเดียว)</option>
            <option value="every">ทำซ้ำทุก N วินาที</option>
          </select>
          <input className={inputCls + ' w-52'} placeholder={modeHint} value={value} onChange={(e) => setValue(e.target.value)} />
          <select className={inputCls} value={userId} onChange={(e) => setUserId(e.target.value)}>
            <option value="">รายงานผลให้ใคร (ไม่บังคับ)</option>
            {Object.entries(users || {}).map(([uid, u]) => <option key={uid} value={uid}>{(u && u.app_name) || uid}</option>)}
          </select>
          <button onClick={add} className="px-4 py-2 rounded-xl2 text-sm font-medium bg-accent/15 text-accent hover:bg-accent/25">ตั้งงาน</button>
        </div>
        {msg && <div className="text-sm text-inkDim mt-2">{msg}</div>}
      </Card>

      {err ? <Spinner text={'โหลดล้มเหลว: ' + err} danger /> : jobs === null ? <Spinner />
        : jobs.length === 0 ? <Card className="p-8 text-center text-inkDim text-sm">ยังไม่มีงานตั้งไว้</Card>
        : jobs.map((j) => (
          <Card key={j.id} className="p-4 flex flex-wrap items-center gap-3">
            <Badge color={j.mode === 'every' ? 'accent2' : 'accent'}>{j.mode === 'every' ? 'ทำซ้ำ' : 'ครั้งเดียว'}</Badge>
            <div className="flex-1 min-w-[220px]">
              <div className="font-medium">{j.name}</div>
              <div className="text-sm text-inkDim">{j.task}</div>
            </div>
            <div className="text-xs text-inkXdim text-right">
              <div>รอบถัดไป {thDate(j.next_run)}</div>
              {j.user_id && <div>รายงานให้ {j.user_id}</div>}
            </div>
            <button onClick={() => del(j)} className="text-danger/70 hover:text-danger text-sm px-2">ยกเลิก</button>
          </Card>
        ))}
    </div>
  );
}

// ── แท็บ: เหตุการณ์ (feed สดจากระบบ event-driven) ───────────────────────────
const EV_BADGE = { device: 'accent', node: 'accent2', phone: 'ok', rule: 'accent', job: 'dim' };
const EV_LABEL = { device: 'อุปกรณ์', node: 'บอร์ด', phone: 'มือถือ', rule: 'กฎยิง', job: 'งาน' };

function EventsTab() {
  const [items, setItems] = useState(null);
  const [err, setErr] = useState('');
  const [filter, setFilter] = useState('');

  const load = useCallback(async () => {
    setErr('');
    try { setItems((await api('/admin/api/events')).reverse()); }
    catch (e) { if (e.message !== 'unauthorized') setErr(e.message); }
  }, []);
  useEffect(() => { load(); }, [load]);

  // รับ event สดจาก websocket (App แปลงมาเป็น CustomEvent ให้)
  useEffect(() => {
    const h = (ev) => setItems((prev) => [ev.detail, ...(prev || [])].slice(0, 300));
    window.addEventListener('syn-event', h);
    return () => window.removeEventListener('syn-event', h);
  }, []);

  const shown = (items || []).filter((it) => !filter || it.kind === filter);
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="font-semibold text-lg">เหตุการณ์ในระบบ <span className="text-inkDim text-sm font-normal">· สด — อุปกรณ์เปลี่ยนค่า/บอร์ดเข้าออก/กฎยิง</span></h2>
        <div className="flex gap-1.5">
          {['', 'device', 'node', 'rule', 'phone'].map((k) => (
            <button key={k} onClick={() => setFilter(k)}
              className={'px-3 py-1.5 rounded-lg text-xs ' + (filter === k ? 'bg-accent/15 text-accent' : 'text-inkDim hover:bg-white/5')}>
              {k === '' ? 'ทั้งหมด' : EV_LABEL[k]}
            </button>
          ))}
        </div>
      </div>
      {err ? <Spinner text={'โหลดล้มเหลว: ' + err} danger /> : items === null ? <Spinner />
        : shown.length === 0 ? <Card className="p-8 text-center text-inkDim text-sm">ยังไม่มีเหตุการณ์ (เก็บเฉพาะตั้งแต่ Hub เปิดรอบนี้)</Card>
        : <Card className="p-2 divide-y divide-line/50 max-h-[75vh] overflow-y-auto">
          {shown.map((it, i) => (
            <div key={i} className="flex items-center gap-3 px-3 py-2 text-sm">
              <span className="text-xs text-inkXdim font-mono w-36 shrink-0">{thDate(it.ts)}</span>
              <Badge color={EV_BADGE[it.kind] || 'dim'}>{EV_LABEL[it.kind] || it.kind}</Badge>
              <span className="flex-1">{it.text}</span>
              {it.detail && <span className="text-xs text-inkXdim truncate max-w-[280px]">{it.detail}</span>}
            </div>
          ))}
        </Card>}
    </div>
  );
}

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
        } else if (m.type === 'device_update') {
          window.dispatchEvent(new CustomEvent('syn-device-update', { detail: { topic: m.topic, state: m.state } }));
        } else if (m.type === 'event') {
          window.dispatchEvent(new CustomEvent('syn-event', { detail: m.entry }));
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
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-5 overflow-x-hidden">
        <div style={{ display: tab === 'users' ? '' : 'none' }}>
          <motion.div animate={tab === 'users' ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 8, scale: 0.99 }} transition={{ duration: 0.25, ease: 'easeOut' }}>
            <UsersTab users={users} reloadUsers={reloadUsers} liveUpdate={liveUpdate} />
          </motion.div>
        </div>
        <div style={{ display: tab === 'devices' ? '' : 'none' }}>
          <motion.div animate={tab === 'devices' ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 8, scale: 0.99 }} transition={{ duration: 0.25, ease: 'easeOut' }}>
            <DevicesTab />
          </motion.div>
        </div>
        <div style={{ display: tab === 'rules' ? '' : 'none' }}>
          <motion.div animate={tab === 'rules' ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 8, scale: 0.99 }} transition={{ duration: 0.25, ease: 'easeOut' }}>
            <RulesTab users={users} />
          </motion.div>
        </div>
        <div style={{ display: tab === 'jobs' ? '' : 'none' }}>
          <motion.div animate={tab === 'jobs' ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 8, scale: 0.99 }} transition={{ duration: 0.25, ease: 'easeOut' }}>
            <JobsTab users={users} />
          </motion.div>
        </div>
        <div style={{ display: tab === 'events' ? '' : 'none' }}>
          <motion.div animate={tab === 'events' ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 8, scale: 0.99 }} transition={{ duration: 0.25, ease: 'easeOut' }}>
            <EventsTab />
          </motion.div>
        </div>
        <div style={{ display: tab === 'location' ? '' : 'none' }}>
          <motion.div animate={tab === 'location' ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 8, scale: 0.99 }} transition={{ duration: 0.25, ease: 'easeOut' }}>
            <LocationTab users={users} liveUpdate={liveUpdate} activeTab={tab} />
          </motion.div>
        </div>
        <div style={{ display: tab === 'agent' ? '' : 'none' }}>
          <motion.div animate={tab === 'agent' ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 8, scale: 0.99 }} transition={{ duration: 0.25, ease: 'easeOut' }}>
            <AgentTab users={users} msgs={agentMsgs} setMsgs={setAgentMsgs} ctxUser={agentCtxUser} setCtxUser={setAgentCtxUser} />
          </motion.div>
        </div>
        <div style={{ display: tab === 'system' ? '' : 'none' }}>
          <motion.div animate={tab === 'system' ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 8, scale: 0.99 }} transition={{ duration: 0.25, ease: 'easeOut' }}>
            <SystemTab />
          </motion.div>
        </div>
        <div style={{ display: tab === 'settings' ? '' : 'none' }}>
          <motion.div animate={tab === 'settings' ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 8, scale: 0.99 }} transition={{ duration: 0.25, ease: 'easeOut' }}>
            <SettingsTab onTokenSaved={reloadUsers} />
          </motion.div>
        </div>
      </main>
      {hubDown && <HubOffline />}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);

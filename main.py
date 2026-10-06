from __future__ import annotations
import os, sys, sqlite3, tempfile, threading, time, hashlib, shutil
from pathlib import Path
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

APP="TikTokAutoPublisher"; EXTS={".mp4",".mov",".mkv",".webm"}
def data_dir():
    p=Path(os.getenv("LOCALAPPDATA",Path.home()))/APP; p.mkdir(parents=True,exist_ok=True); return p
def db_path(): return data_dir()/"publisher.sqlite3"
class DB:
    def __init__(self,path=None):
        self.path=Path(path or db_path()); self.path.parent.mkdir(parents=True,exist_ok=True); self.lock=threading.RLock(); self.init()
    def con(self):
        c=sqlite3.connect(self.path,timeout=30); c.row_factory=sqlite3.Row; c.execute("PRAGMA journal_mode=WAL"); return c
    def init(self):
        with self.con() as c:
            c.executescript("""CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY,name TEXT NOT NULL,folder TEXT NOT NULL,profile TEXT NOT NULL,enabled INTEGER DEFAULT 1,status TEXT DEFAULT 'OFFLINE',daily_limit INTEGER DEFAULT 3);
CREATE TABLE IF NOT EXISTS videos(id INTEGER PRIMARY KEY,account_id INTEGER NOT NULL,filename TEXT,filepath TEXT,status TEXT DEFAULT 'WAITING',added TEXT,scheduled TEXT,attempts INTEGER DEFAULT 0,error TEXT,fingerprint TEXT,UNIQUE(account_id,fingerprint));
CREATE TABLE IF NOT EXISTS schedules(id INTEGER PRIMARY KEY,account_id INTEGER,time TEXT);
CREATE TABLE IF NOT EXISTS logs(id INTEGER PRIMARY KEY,ts TEXT,account_id INTEGER,video_id INTEGER,action TEXT,message TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
""")
            c.execute("INSERT OR IGNORE INTO settings VALUES('post_publish_action','delete')")
            c.execute("INSERT OR IGNORE INTO settings VALUES('retry_count','2')")
            c.execute("INSERT OR IGNORE INTO settings VALUES('retry_delay_minutes','10')")
    def q(self,sql,args=()):
        with self.lock,self.con() as c: return c.execute(sql,args).fetchall()
    def x(self,sql,args=()):
        with self.lock,self.con() as c: cur=c.execute(sql,args); c.commit(); return cur.lastrowid
def fp(p):
    s=p.stat(); return hashlib.sha256(f"{str(p.resolve()).lower()}|{s.st_size}|{s.st_mtime_ns}".encode()).hexdigest()
def add_video(db,aid,p):
    p=Path(p)
    if p.suffix.lower() not in EXTS or not p.is_file(): return False
    try: db.x("INSERT INTO videos(account_id,filename,filepath,status,added,fingerprint) VALUES(?,?,?,?,?,?)",(aid,p.name,str(p),"WAITING",datetime.now().isoformat(timespec="seconds"),fp(p))); return True
    except sqlite3.IntegrityError: return False
def scan(db,aid,folder):
    items=[p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in EXTS]
    items.sort(key=lambda p:(p.stat().st_ctime_ns,p.name.lower()))
    return sum(add_video(db,aid,p) for p in items)
def stable(p,checks=3,delay=.5):
    last=None
    for _ in range(checks):
        try: cur=(p.stat().st_size,p.stat().st_mtime_ns)
        except OSError:return False
        if last==cur and cur[0]>0: pass
        last=cur; time.sleep(delay)
    try:return (p.stat().st_size,p.stat().st_mtime_ns)==last and last[0]>0
    except OSError:return False
class Handler(FileSystemEventHandler):
    def __init__(self,db,aid): self.db=db; self.aid=aid
    def _go(self,path):
        p=Path(path)
        if p.suffix.lower() in EXTS: threading.Thread(target=lambda: add_video(self.db,self.aid,p) if stable(p) else None,daemon=True).start()
    def on_created(self,e):
        if not e.is_directory:self._go(e.src_path)
    def on_moved(self,e):
        if not e.is_directory:self._go(e.dest_path)
class Watchers:
    def __init__(self,db): self.db=db; self.obs=[]
    def start(self):
        for a in self.db.q("SELECT * FROM accounts WHERE enabled=1"):
            if Path(a["folder"]).is_dir():
                o=Observer(); o.schedule(Handler(self.db,a["id"]),a["folder"],recursive=False); o.start(); self.obs.append(o)
    def stop(self):
        for o in self.obs:o.stop()
        for o in self.obs:o.join(3)
def selftest():
    try:
        os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
        from PySide6.QtWidgets import QApplication
        app=QApplication.instance() or QApplication([]); assert app
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            r=Path(td); v=r/"videos"; v.mkdir(); d=DB(r/"x.sqlite")
            aid=d.x("INSERT INTO accounts(name,folder,profile) VALUES(?,?,?)",("A",str(v),str(r/"profile")))
            for i in range(5):(v/f"{i}.mp4").write_bytes(b"x"*10)
            assert scan(d,aid,v)==5 and scan(d,aid,v)==0
            w=Watchers(d); w.start(); (v/"new.mp4").write_bytes(b"new")
            end=time.time()+8
            while time.time()<end and not d.q("SELECT 1 FROM videos WHERE filename='new.mp4'"): time.sleep(.2)
            w.stop(); assert d.q("SELECT 1 FROM videos WHERE filename='new.mp4'")
            d2=DB(r/"x.sqlite"); assert len(d2.q("SELECT * FROM videos"))==6
        print("SELF-TEST OK"); return 0
    except Exception:
        import traceback; traceback.print_exc(); return 1
def gui():
    from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QPushButton,QLabel,QTableWidget,QTableWidgetItem,QTabWidget,QFileDialog,QInputDialog,QMessageBox,QComboBox
    from PySide6.QtCore import QTimer
    app=QApplication(sys.argv); app.setStyleSheet("""QWidget{background:#121417;color:#eee;font:14px 'Segoe UI'} QPushButton{background:#242a31;border:1px solid #38414b;padding:9px 16px;border-radius:6px} QPushButton:hover{background:#303842} QTableWidget{background:#181c21;gridline-color:#333} QHeaderView::section{background:#242a31;padding:7px}""")
    db=DB(); watchers=Watchers(db)
    class W(QMainWindow):
        def __init__(self):
            super().__init__(); self.setWindowTitle("TikTok Auto Publisher"); self.resize(1100,700); self.state="STOPPED"
            tabs=QTabWidget(); self.setCentralWidget(tabs)
            dash=QWidget(); dl=QVBoxLayout(dash); self.status=QLabel("● STOPPED"); dl.addWidget(self.status)
            row=QHBoxLayout()
            for text,state in [("START","RUNNING"),("PAUSE","PAUSED"),("STOP","STOPPED")]:
                b=QPushButton(text); b.clicked.connect(lambda _,s=state:self.setstate(s)); row.addWidget(b)
            r=QPushButton("REFRESH"); r.clicked.connect(self.refresh); row.addWidget(r); dl.addLayout(row); self.metrics=QLabel(); dl.addWidget(self.metrics); tabs.addTab(dash,"Dashboard")
            acc=QWidget(); al=QVBoxLayout(acc); add=QPushButton("Add Account"); add.clicked.connect(self.add_account); al.addWidget(add); self.at=QTableWidget(0,6); self.at.setHorizontalHeaderLabels(["Account","Status","Videos","Daily Limit","Chrome Profile","Folder"]); al.addWidget(self.at); tabs.addTab(acc,"Accounts")
            q=QWidget(); ql=QVBoxLayout(q); self.qt=QTableWidget(0,6); self.qt.setHorizontalHeaderLabels(["Filename","Status","Added","Scheduled","Attempts","Error"]); ql.addWidget(self.qt); tabs.addTab(q,"Queue")
            sch=QWidget(); sl=QVBoxLayout(sch); sl.addWidget(QLabel("Schedules are stored per account in SQLite. Add times as HH:MM using the account editor in future updates.")); tabs.addTab(sch,"Schedule")
            act=QWidget(); ll=QVBoxLayout(act); self.lt=QTableWidget(0,3); self.lt.setHorizontalHeaderLabels(["Time","Action","Message"]); ll.addWidget(self.lt); tabs.addTab(act,"Activity")
            st=QWidget(); stl=QVBoxLayout(st); stl.addWidget(QLabel("Post-Publish Action")); self.action=QComboBox(); self.action.addItems(["Delete permanently","Move to Archive"]); stl.addWidget(self.action); tabs.addTab(st,"Settings")
            QTimer.singleShot(0,self.startup); self.timer=QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(3000)
        def startup(self):
            for a in db.q("SELECT * FROM accounts WHERE enabled=1"):
                if Path(a["folder"]).is_dir(): threading.Thread(target=scan,args=(db,a["id"],a["folder"]),daemon=True).start()
            watchers.start(); self.refresh()
        def setstate(self,s): self.state=s; self.status.setText("● "+s)
        def add_account(self):
            name,ok=QInputDialog.getText(self,"Add Account","Account name:")
            if not ok or not name:return
            folder=QFileDialog.getExistingDirectory(self,"Video Folder")
            if not folder:return
            profile=str(data_dir()/"chrome_profiles"/name.replace(" ","_")); Path(profile).mkdir(parents=True,exist_ok=True)
            aid=db.x("INSERT INTO accounts(name,folder,profile) VALUES(?,?,?)",(name,folder,profile)); scan(db,aid,folder); QMessageBox.information(self,"Added","Account added and existing videos scanned."); self.refresh()
        def refresh(self):
            accounts=db.q("SELECT * FROM accounts"); waiting=db.q("SELECT COUNT(*) n FROM videos WHERE status='WAITING'")[0]["n"]; failed=db.q("SELECT COUNT(*) n FROM videos WHERE status='FAILED'")[0]["n"]
            self.metrics.setText(f"Total Accounts: {len(accounts)}     Waiting Videos: {waiting}     Failed: {failed}")
            self.at.setRowCount(len(accounts))
            for i,a in enumerate(accounts):
                n=db.q("SELECT COUNT(*) n FROM videos WHERE account_id=?",(a["id"],))[0]["n"]
                for j,x in enumerate([a["name"],a["status"],n,a["daily_limit"],a["profile"],a["folder"]]): self.at.setItem(i,j,QTableWidgetItem(str(x)))
            vids=db.q("SELECT * FROM videos ORDER BY id DESC LIMIT 1000"); self.qt.setRowCount(len(vids))
            for i,v in enumerate(vids):
                for j,x in enumerate([v["filename"],v["status"],v["added"],v["scheduled"] or "",v["attempts"],v["error"] or ""]):self.qt.setItem(i,j,QTableWidgetItem(str(x)))
            logs=db.q("SELECT * FROM logs ORDER BY id DESC LIMIT 500"); self.lt.setRowCount(len(logs))
            for i,l in enumerate(logs):
                for j,x in enumerate([l["ts"],l["action"],l["message"]]):self.lt.setItem(i,j,QTableWidgetItem(str(x)))
        def closeEvent(self,e): watchers.stop(); e.accept()
    w=W(); w.show(); return app.exec()
if __name__=="__main__": raise SystemExit(selftest() if "--self-test" in sys.argv else gui())

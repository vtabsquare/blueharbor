"""One Postgres LISTEN connection; authorized SSE clients re-read scoped records."""
import threading
import time
import cloud_config as cfg
condition=threading.Condition()
generation=0
status='STARTING'

def trigger():
    global generation
    with condition:
        generation+=1
        condition.notify_all()

def wait(previous,timeout=15):
    with condition:
        condition.wait_for(lambda:generation!=previous,timeout)
        return generation

def start(stop):
    def run():
        global generation,status
        import psycopg
        while not stop.is_set():
            try:
                with psycopg.connect(cfg.DSN,autocommit=True,sslmode='require',connect_timeout=10,prepare_threshold=None) as con:
                    con.execute('LISTEN blueharbor_changed');status='CONNECTED'
                    while not stop.is_set():
                        for _ in con.notifies(timeout=2):
                            with condition:generation+=1;condition.notify_all()
            except Exception:status='RECONNECTING';stop.wait(3)
        status='STOPPED'
    threading.Thread(target=run,name='supabase-change-listener',daemon=True).start()

# hn

Console in sola lettura per seguire e far crescere, in modo pulito, la reputazione di `francescobianco` su Hacker News.
Non pubblica, non vota e non genera commenti: quello che si scrive su HN lo scrivi tu.

```
./hn.py status            # karma attuale e delta dall'ultima esecuzione (storico in data/karma.jsonl)
./hn.py audit             # storico, item dead, autopromozione, avvisi
./hn.py discover linux c  # thread giovani sui tuoi temi dove un commento presto è utile
./hn.py replies           # tuoi commenti che hanno ricevuto risposte
```

Utente diverso: `HN_USER=nome ./hn.py status`.

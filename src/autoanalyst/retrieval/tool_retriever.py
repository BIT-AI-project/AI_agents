import math, re
from collections import Counter

class ToolRetriever:
    """Small BM25-style retriever with domain tag boosting, no vector service required."""
    def __init__(self, summaries: list[dict], top_k: int=4):
        self.summaries=summaries; self.top_k=top_k
    @staticmethod
    def tokens(text): return re.findall(r"[a-z0-9_]+",text.lower())
    def retrieve(self,query: str) -> list[dict]:
        q=self.tokens(query); docs=[]
        for item in self.summaries:
            corpus=" ".join(str(item.get(k,"")) for k in ("name","description","long_description","tags","capabilities","examples"))
            docs.append(self.tokens(corpus))
        df=Counter(t for doc in docs for t in set(doc)); avg=sum(map(len,docs))/max(len(docs),1); scored=[]
        domain={"sql":"sql","database":"sql","query":"sql","sales":"sales","region":"region","chart":"chart","visualization":"visualization","plot":"chart","report":"report","markdown":"markdown","compare":"comparison","product":"product","python":"python"}
        for item,doc in zip(self.summaries,docs):
            counts=Counter(doc); score=0.0
            for term in set(q):
                if term not in counts: continue
                idf=math.log(1+(len(docs)-df[term]+.5)/(df[term]+.5)); tf=counts[term]
                score+=idf*(tf*2.2)/(tf+1.2*(.25+.75*len(doc)/max(avg,1)))
                if term in domain and domain[term] in item.get("tags",[]): score+=1.5
            scored.append((score,item))
        scored.sort(key=lambda pair:(pair[0],pair[1]["name"]),reverse=True)
        selected=[dict(item, retrieval_score=round(score,4)) for score,item in scored[:self.top_k] if score>0]
        if not selected:
            fallback={"sql_schema_inspect","sql_query","python_execute","save_markdown_report"}
            selected=[dict(item,retrieval_score=0.0) for item in self.summaries if item["name"] in fallback][:self.top_k]
        return selected

"use client";
import { useGame } from "@/lib/store";

export function QuestJournal() {
  const quests = useGame((s) => s.view?.quests) || [];
  const abandon = useGame((s) => s.abandonQuest);
  const groups: [string, string[]][] = [["Active", ["ACTIVE"]], ["Offered", ["AVAILABLE"]], ["Completed", ["COMPLETED"]], ["Failed / abandoned", ["FAILED", "ABANDONED"]]];
  return (
    <div className="space-y-5" data-testid="quest-journal">
      {quests.length === 0 && <p className="text-muted">Your journal is empty. Talk to the people of Veyr.</p>}
      {groups.map(([title, sts]) => {
        const qs = quests.filter((q) => sts.includes(q.status));
        if (!qs.length) return null;
        return (
          <section key={title}>
            <h3 className="text-gold mb-2">{title}</h3>
            <ul className="space-y-3">
              {qs.map((q) => (
                <li key={q.id} className="border border-edge rounded-md p-3 bg-panel2" data-testid={`quest-${q.id}`}>
                  <div className="flex justify-between"><h4 className="font-serif">{q.title}</h4><span className="text-[10px] uppercase text-muted">{q.category}</span></div>
                  <p className="text-xs text-muted mt-1">{q.description}</p>
                  <ul className="text-sm mt-2 space-y-0.5">{q.objectives.map((o) => <li key={o.id} className={o.done ? "text-leaf" : ""}>{o.done ? "☑" : "☐"} {o.text}</li>)}</ul>
                  {q.outcome_text && <p className="text-sm italic text-goldDim mt-2">{q.outcome_text}</p>}
                  {q.status === "ACTIVE" && q.category !== "main" && <button className="btn text-xs mt-2" onClick={() => void abandon(q.id)}>Abandon</button>}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

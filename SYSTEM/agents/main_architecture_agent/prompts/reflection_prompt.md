# Self-Learning Reflection Prompt

Analyze the provided batch of completed task experiences and identify systematic patterns:
1. Identify recurring routing failures or suboptimal agent selection.
2. Detect missing prerequisites or dependency ordering errors.
3. Quantify duration and retry statistics per agent.
4. Review user corrections and explicit feedback to find structural planning flaws.
5. For each identified finding, generate a Lesson with:
   - `lesson_type`: classification
   - `confidence`: statistical confidence based on evidence count
   - `recommended_action`: concrete adjustment to routing preferences or fallback rules
   - `supporting_experience_ids`: list of source experiences

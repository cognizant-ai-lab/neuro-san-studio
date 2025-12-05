# Therapy Vignette Supervision

The **Therapy Vignette Supervision** system is a multi-agent system that takes a therapy vignette and produces a
treatment plan which is the result of consensus amongst a number of different therapy experts.

## File

[therapy_vignette_supervisors.hocon](../../../registries/industry/therapy_vignette_supervisors.hocon)

---

## Description

Provide the top-level "front-man" agent a therapy vignette and get a consensus treatment plan based on the opinions of a
number of different therapy experts.

---

## Example Conversation

### Human

```text
Ali and Maryam are a married couple in their 40s who have been experiencing relationship difficulties. They report
frequent arguments, communication breakdowns, and a lack of intimacy. Both are committed to working on their marriage
and are seeking counseling to improve their relationship. The challenges in Ali and Maryam's relationship have
significantly affected their jobs and their parenting of two children, ages 4 and 2. Ali immigrated to the US from Iran
as a child, while Maryam moved to the US from Iran six years ago. Maryam is a practicing Muslim, and Ali does not
practice Islam, which has contributed to their differing parenting styles and their relationship with their in-laws.
Ali's family lives in the same town. Maryam feels that her mother-in-law is controlling their life, whereas Ali believes
his mother is merely providing support for his family. Maryam is currently unemployed, primarily due to language
barriers, and is also the primary caregiver for their two young children at home.
```

### AI (therapy_supervisor)

```markdown
1. **Diagnostic Assessment**: Ali and Maryam are experiencing significant relationship distress, characterized by
frequent arguments, communication breakdowns, and a lack of intimacy. The challenges have impacted their parenting and
work life, and cultural differences, religious practices, and family dynamics are contributing factors. Maryam may be
experiencing acculturation stress due to recent immigration and language barriers. Their symptoms suggest relational
issues with a focus on cultural and interpersonal conflict.

2. **Therapeutic Goals**: The primary goals include improving communication skills to reduce misunderstandings and
conflicts, developing strategies for managing cultural and religious differences, enhancing intimacy, and rebuilding
trust within the marriage. Additionally, fostering self-awareness and self-leadership in both partners can help them
approach their relationship from a place of calmness, curiosity, and compassion.

3. **Interventions**: Interventions will focus on evidence-based techniques that enhance communication and emotional
connection. Mindfulness exercises will be used to increase awareness of thoughts and emotional responses, while
cognitive restructuring techniques will help challenge unhelpful thoughts contributing to conflict. Communication skills
training will provide tools for constructive expression of needs and concerns. Additionally, values clarification will
help align actions with what truly matters in their relationship and parenting, and guided meditations will facilitate
internal dialogues to understand underlying concerns and fears.

4. **Ethical Considerations**: Respecting and understanding the cultural and religious backgrounds of Ali and Maryam is
crucial. The therapeutic process should be sensitive to Maryam's experience as a recent immigrant, her language barriers,
and the potential power dynamics in their relationship. Ensuring both partners feel heard and respected is vital,
especially when addressing cultural and religious differences. Confidentiality, informed consent, and maintaining a
non-judgmental stance are fundamental ethical considerations throughout the therapy process.
```

---

## Architecture Overview

### Frontman Agent: **therapy_supervisor**

* Acts as the entry point for all user commands
* Can call act_expert, ifs_expert, eft_expert, cbt_expert, and dbt_expert

---

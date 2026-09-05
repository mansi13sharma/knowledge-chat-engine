from openai import OpenAI

from app.core.config import settings

_client = OpenAI(api_key=settings.openai_api_key)


def chat_completion(
    system_prompt: str,
    user_prompt: str,
    temperature: float | None = None,
) -> str:
    kwargs = {} if temperature is None else {"temperature": temperature}

    response = _client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        **kwargs,
    )

    return response.choices[0].message.content or ""


# # from groq import Groq
# from openai import OpenAI

# from app.core.config import settings

# _client = OpenAI(api_key=settings.openai_api_key)
# # _client = Groq(api_key=settings.groq_api_key)



# def chat_completion(system_prompt: str, user_prompt: str, temperature: float | None = None) -> str:
#     kwargs = {} if temperature is None else {"temperature": temperature}
#     response = _client.chat.completions.create(
#         model=settings.groq_model,
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": user_prompt},
#         ],
#         **kwargs,
#     )
#     return response.choices[0].message.content or ""

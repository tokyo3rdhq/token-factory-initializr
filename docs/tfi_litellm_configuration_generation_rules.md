## LiteLLM Configuration Generation Rules

When generating or modifying LiteLLM configuration, follow the rules below to ensure that `litellm_params.model` uses the correct LiteLLM provider adapter for the model's API protocol.

### 1. Model ID Mapping

Determine the LiteLLM model string using the following rules **in order**:

**Rule 1 — Decision models**

If the model's `architecture.output` contains `decision`, or its normalized `output` field contains `decision`, use:

`hosted_vllm/${model_id}`

This rule takes precedence over the data-source-specific mapping rules below and applies regardless of the model's `data_source`.

For example, an AMD Radeon Clef model with canonical model ID `Clef` must use:

`hosted_vllm/Clef`

LiteLLM's `hosted_vllm/` adapter is used for this class of decision API. The adapter determines the appropriate decision endpoint path, such as `/v1/systemone` or `/v1/decisions`, according to the supported model integration. Do not manually append these paths to `api_base`.

**Rule 2 — Non-decision models**

If the model does not declare `decision` in its output modalities, apply the following data-source mapping:

| `data_source` | `litellm_params.model` |
| ------------- | --------------------- |
| `nvidia` | `nvidia_nim/${model_id}` |
| `amd` | `openai/${model_id}` |
| `kilo` | `openai/${model_id}` |
| `openrouter` | `openrouter/${model_id}` |
| `huggingface` | `huggingface/${provider}/${model_id}` |

Where:

- `${model_id}` is the model's native identifier from the relevant TFI model or endpoint data. Use the identifier required by the selected LiteLLM integration; do not replace it with the canonical catalog ID if those identifiers differ.
- `${provider}` is the Hugging Face inference provider associated with the model, as returned by TFI. Do not substitute the data-source name or invent a provider value.
- The decision-model rule takes precedence over all mappings in this table.

### 2. ADD Entry Requirements

When generating an `ADD` entry for LiteLLM:

1. Read the model's `data_source`, model identifier, and `output_modalities` from TFI model data. Read the relevant endpoint information when needed to determine the native model ID and `api_base`.
2. Check whether `output_modalities` contains `decision` before applying the data-source mapping.
3. For decision models, set `litellm_params.model` to `hosted_vllm/${model_id}`.
4. For non-decision models, apply the data-source mapping in Section 1.
5. Preserve the existing configuration's naming conventions for `model_name` and other fields.
6. Do not confuse `model_name` (the alias exposed to clients) with `litellm_params.model` (the model identifier used by LiteLLM to select its provider adapter and route requests).
7. Use the `api_base` associated with the selected endpoint. Do not assume that every provider uses the same base URL or API path.

### 3. Decision Model Handling

- Identify decision models by the explicit `decision` output modality, not by the model name or by `reasoning`, `tools`, or `structured_output` capabilities alone.
- Apply the `hosted_vllm/` prefix to decision models regardless of their data source, provided the selected LiteLLM integration supports this adapter for that model.
- Keep the original model and endpoint identifiers unchanged in TFI's catalog. Add the LiteLLM prefix only when generating LiteLLM configuration.
- Do not modify `api_base` merely because a model is a decision model. For example, the verified AMD Radeon endpoint base URL may remain `https://developer.amd.com.cn/radeon/api/v1`; LiteLLM's adapter handles the appropriate request path.
- Do not manually append `/v1/systemone` or `/v1/decisions` to `api_base` unless the applicable integration explicitly requires it.
- If output modality metadata is missing or does not establish that the model is a decision model, do not infer the decision mapping from the model name alone. Use the regular mapping or request clarification if the correct adapter cannot be determined.

### 4. Missing or Unsupported Data

- If a required field is missing, do not guess its value.
- If `data_source` is not covered by the mapping, do not invent a LiteLLM prefix.
- If the model declares `decision` but the relevant LiteLLM integration cannot be verified, consult the applicable LiteLLM integration documentation or request clarification rather than generating a potentially invalid configuration.
- Do not assume that these rules apply to NewAPI, Bifrost, or other configuration targets. Use their respective configuration conventions.

### 5. Existing Configuration Compatibility

When adding models to an existing LiteLLM configuration, preserve the existing structure and conventions. Only modify unrelated entries when explicitly requested.

The generated `litellm_params.model` must follow the mapping and precedence rules above. Remaining fields, including `api_base` and `api_key`, must follow the selected endpoint's configuration and authentication requirements.

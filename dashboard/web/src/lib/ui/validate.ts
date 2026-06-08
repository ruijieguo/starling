/** 返回缺失的必填字段名。LLM:key 必填(否则无法抽取);Embedder:key 选填(无则 stub)。 */
export function missingFields(
	p: { model: string },
	opts: { keyRequired: boolean; keySet: boolean; keyInput: string }
): string[] {
	const miss: string[] = [];
	if (!p.model.trim()) miss.push('model');
	if (opts.keyRequired && !opts.keySet && !opts.keyInput.trim()) miss.push('api_key');
	return miss;
}

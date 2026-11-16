# Push the paired-eval notebook to Kaggle

1. Install the Kaggle CLI/API (one time):
   `python -m pip install kaggle`
2. Export your token (already at ~/.kaggle/access_token):
   `export KAGGLE_API_TOKEN=$(cat ~/.kaggle/access_token)`
   or put `{"username":"...","key":"..."}` in ~/.kaggle/kaggle.json
3. Update `kernel-metadata.json` `id` with your Kaggle username if needed.
4. From this folder:
   `cd notebooks && kaggle kernels push -p .`
5. Monitor: `kaggle kernels status stewartbarteau/gemma4-e4b-paired-v4-v6`
6. Pull outputs later: `kaggle kernels output stewartbarteau/gemma4-e4b-paired-v4-v6 -p ./kernel_output`

Notes:
- The notebook uses the competition model and wheels; enable GPU in Kaggle.
- Submission folders referenced by the notebook are included by Kaggle's tar-up? Verify that `AgenticSubmission/v6_impact` is attached as a dataset or packed into the notebook directory before push if required.
EOF

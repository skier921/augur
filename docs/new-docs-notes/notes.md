The reason for this is because when people add, for example, one repo from an org, that repo would go in a directory for just that org; then, when repos move, the directory would make no sense. So, we simplified the directory structure. You will see in the file_path that the directory structure is common, with the root of the cloned repo in the repo_root parameter directory in augur_operations.config table, so the "file path ends up being: repo_root/repo_id/repo_path on the hard drive where repos are stored.     


# Max Queries
```sql
    SELECT
            e.repo_id,
            augur_data.repo.repo_git,
            augur_data.repo.repo_name,
            e.programming_language,
            e.code_lines,
            e.files
        FROM
            augur_data.repo,
        (SELECT 
            d.repo_id,
            d.programming_language,
            SUM(d.code_lines) AS code_lines,
            COUNT(*)::int AS files
        FROM
            (SELECT
                    augur_data.repo_labor.repo_id,
                    augur_data.repo_labor.programming_language,
                    augur_data.repo_labor.code_lines
                FROM
                    augur_data.repo_labor,
                    ( SELECT 
                            augur_data.repo_labor.repo_id,
                            MAX ( data_collection_date ) AS last_collected
                        FROM 
                            augur_data.repo_labor
                        GROUP BY augur_data.repo_labor.repo_id) recent 
                WHERE
                    augur_data.repo_labor.repo_id = recent.repo_id
                    AND augur_data.repo_labor.data_collection_date > recent.last_collected - (5 * interval '1 minute')) d
        GROUP BY d.repo_id, d.programming_language) e
        WHERE augur_data.repo.repo_id = e.repo_id
        ORDER BY e.repo_id
```
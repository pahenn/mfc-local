-- Column metadata for dbo.CorporationTypes
SELECT  c.COLUMN_NAME
        , c.ORDINAL_POSITION
        , c.DATA_TYPE
        , c.CHARACTER_MAXIMUM_LENGTH
        , c.IS_NULLABLE
        , c.COLUMN_DEFAULT
        , COLUMNPROPERTY(OBJECT_ID('dbo.CorporationTypes'), c.COLUMN_NAME, 'IsIdentity') AS IsIdentity
FROM    INFORMATION_SCHEMA.COLUMNS c
WHERE   c.TABLE_SCHEMA = 'dbo'
        AND c.TABLE_NAME = 'CorporationTypes'
ORDER BY c.ORDINAL_POSITION;

-- Toyota — insert into dbo.CorporationTypes
-- BrandId left at 0; revisit once the upstream brand link is confirmed.

BEGIN TRANSACTION;

INSERT INTO dbo.CorporationTypes (
        CorporationPrefix,
        CorporationType,
        CorporationName,
        HeaderClass,
        HeaderClassValue,
        BrandId,
        ShowOnFleetScreen,
        AIFee,
        AIFeePct,
        AIMinimumFee,
        InvoiceFlatFee,
        InvoicePercentFee,
        AICutFlatFee,
        AICutPercentFee,
        Site_PaymentTypeID,
        AILive,
        GenerateIdCards,
        StoreNumberLength,
        primaryColor,
        useCorporationPrefixAsStorePrefix,
        storeNumberPaddingCharacter
)
VALUES (
        'toy',
        'toyota',
        'Toyota',
        N'headGen',
        N'background-color:#CCCCCC;color:Black;font-weight:bold;',
        0,
        1,
        0.000000,
        0.025000,
        0.000000,
        0.000000,
        0.025000,
        0.000000,
        0.500000,
        1,
        1,
        0,
        6,
        NULL,
        1,
        '0'
);

SELECT  CorporationTypeID,
        CorporationPrefix,
        CorporationType,
        CorporationName,
        BrandId,
        AIFeePct,
        InvoicePercentFee,
        AICutPercentFee,
        StoreNumberLength,
        AILive,
        ShowOnFleetScreen
FROM    dbo.CorporationTypes
WHERE   CorporationType = 'toyota';

ROLLBACK TRANSACTION;
-- COMMIT TRANSACTION;
